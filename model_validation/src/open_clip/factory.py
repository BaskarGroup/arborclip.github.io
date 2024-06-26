import json
import logging
import os
import pathlib
import re
from copy import deepcopy
from pathlib import Path
from typing import Optional, Tuple
from collections import OrderedDict
import pdb
import pickle 
from torchvision import transforms
import torch
from torch import nn

from .constants import OPENAI_DATASET_MEAN, OPENAI_DATASET_STD
from .model import CLIP, VisionModel, convert_weights_to_fp16, resize_pos_embed, SIMCLR
from .openai import load_openai_model
from .pretrained import get_pretrained_cfg, download_pretrained
from .transform import image_transform
from .tokenizer import DEFAULT_CONTEXT_LENGTH, SimpleTokenizer

import open_clip

try:
    from coca_pytorch.coca_pytorch import CoCa
except:
    logging.debug("coca-pytorch is not installed")

try:
    from x_clip import CLIP as XCLIP
    from x_clip.visual_ssl import SimSiam
    from vit_pytorch import ViT
    from vit_pytorch.extractor import Extractor
except:
    logging.debug("xclip is not installed")

try:
    import timm
    from timm.models.vision_transformer import Block
except ImportError as e:
    print(e)
    logging.debug("timm is not installed")

HF_HUB_PREFIX = 'hf-hub:'
_MODEL_CONFIG_PATHS = [Path(__file__).parent / f"model_configs/"]
_MODEL_CONFIGS = {}  # directory (model_name: config) of model architecture configs


class View(nn.Module):
    def __init__(self, shape):
        super().__init__()
        self.shape = shape

    def forward(self, x):
        return x.view(*self.shape)

def _natural_key(string_):
    return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', string_.lower())]


def _rescan_model_configs():
    global _MODEL_CONFIGS

    config_ext = ('.json',)
    config_files = []
    for config_path in _MODEL_CONFIG_PATHS:
        if config_path.is_file() and config_path.suffix in config_ext:
            config_files.append(config_path)
        elif config_path.is_dir():
            for ext in config_ext:
                config_files.extend(config_path.glob(f'*{ext}'))

    for cf in config_files:
        with open(cf, 'r') as f:
            model_cfg = json.load(f)
            if all(a in model_cfg for a in ('embed_dim', 'vision_cfg', 'text_cfg')) or (a in model_cfg for a in ('embed_dim', 'vision_cfg')):
                _MODEL_CONFIGS[cf.stem] = model_cfg

    _MODEL_CONFIGS = {k: v for k, v in sorted(_MODEL_CONFIGS.items(), key=lambda x: _natural_key(x[0]))}


_rescan_model_configs()  # initial populate of model config registry


def load_state_dict(checkpoint_path: str, map_location='cpu'):
    checkpoint = torch.load(checkpoint_path, map_location=map_location)
    if isinstance(checkpoint, dict) and 'state_dict' in checkpoint:
        state_dict = checkpoint['state_dict']
    elif isinstance(checkpoint, dict) and 'model' in checkpoint:
        #This converts from "Hydra" format into "Timm" format
        state_dict = checkpoint['model']
        for k in list(state_dict.keys()):
            state_dict["visual.trunk."+k] = state_dict[k]
            del state_dict[k]
        state_dict["visual.head.proj.weight"] = state_dict["visual.trunk.head.weight"]
        state_dict["visual.head.proj.bias"] = state_dict["visual.trunk.head.bias"]
        del state_dict["visual.trunk.head.weight"]
        del state_dict["visual.trunk.head.bias"]
        state_dict["logit_scale"] = torch.tensor([1.0])
    else:
        state_dict = checkpoint
    if next(iter(state_dict.items()))[0].startswith('module'):
        state_dict = {k[7:]: v for k, v in state_dict.items()}
    return state_dict


def load_checkpoint(model, checkpoint_path, strict=False):
    print(f"Loading checkpoint from {checkpoint_path}")
    state_dict = load_state_dict(checkpoint_path)
    resize_pos_embed(state_dict, model)
    try:
        incompatible_keys = model.load_state_dict(state_dict, strict=strict)
    except:
        for k in list(state_dict.keys()):
            state_dict["visual.trunk."+k] = state_dict[k]
            del state_dict[k]
        incompatible_keys = model.load_state_dict(state_dict, strict=strict)
    if len(incompatible_keys.missing_keys) > 0:
        logging.warning(f"Missing keys: {incompatible_keys.missing_keys}")
    return incompatible_keys

#Changed from Sync
#("bn2", nn.SyncBatchNorm(mlp_dim))
def build_mlp(in_dim, mlp_dim, out_dim):
    return nn.Sequential(OrderedDict([
        ("layer1", nn.Linear(in_dim, mlp_dim)),
        ("bn1", nn.BatchNorm1d(mlp_dim)),
        ("relu1", nn.ReLU(inplace=True)),
        ("layer2", nn.Linear(mlp_dim, mlp_dim)),
        ("bn2", nn.BatchNorm1d(mlp_dim)),
        ("relu2", nn.ReLU(inplace=True)),
        ("layer3", nn.Linear(mlp_dim, out_dim)),
    ]))

def get_model_config(model_name):
    if model_name in _MODEL_CONFIGS:
        return deepcopy(_MODEL_CONFIGS[model_name])
    else:
        return None

def get_tokenizer(
        model_name: str = '',
        context_length: Optional[int] = None,
        **kwargs,
):
    if model_name.startswith(HF_HUB_PREFIX):
        model_name = model_name[len(HF_HUB_PREFIX):]
        try:
            config = _get_hf_config(model_name)['model_cfg']
        except Exception:
            tokenizer = HFTokenizer(
                model_name,
                context_length=context_length or DEFAULT_CONTEXT_LENGTH,
                **kwargs,
            )
            return tokenizer
    else:
        config = get_model_config(model_name)
        assert config is not None, f"No valid model config found for {model_name}."

    text_config = config.get('text_cfg', {})
    if 'tokenizer_kwargs' in text_config:
        tokenizer_kwargs = dict(text_config['tokenizer_kwargs'], **kwargs)
    else:
        tokenizer_kwargs = kwargs

    if context_length is None:
        context_length = text_config.get('context_length', DEFAULT_CONTEXT_LENGTH)

    if 'hf_tokenizer_name' in text_config:
        tokenizer = HFTokenizer(
            text_config['hf_tokenizer_name'],
            context_length=context_length,
            **tokenizer_kwargs,
        )
    else:
        tokenizer = SimpleTokenizer(
            context_length=context_length,
            **tokenizer_kwargs,
        )

    return tokenizer

def create_model(
        model_name: str,
        pretrained: str = '',
        precision: str = 'fp32',
        device: torch.device = torch.device('cpu'),
        jit: bool = False,
        force_quick_gelu: bool = False,
        pretrained_image: bool = False,
        cache_dir: Optional[str] = None,
        filip: bool = False,
        dcl: bool = False,
        elp: bool = False,
        vssl: bool = False,
        mlm: bool = False,
        simclr: bool = False,
        imsize: int = 224
):
    if model_name == "xclip" or any([filip, mlm, vssl, elp, dcl]):
        if vssl:
            base_vit = ViT(
                image_size = 256,
                patch_size = 32,
                num_classes = 1000,
                dim = 512,
                depth = 6,
                heads = 16,
                mlp_dim = 2048,
                dropout = 0.1,
                emb_dropout = 0.1
            )
            enc = Extractor(
                base_vit,
                return_embeddings_only = True
            )
            visual_ssl = SimSiam(                 # SimSiam defined externally - needs to be a module that accepts an image of the same dimensions as CLIP and returns a scalar loss
                enc,
                image_size = 256,
                hidden_layer = -1
            )
            model = XCLIP(
                image_encoder = enc,
                dim_image = 512,
                dim_text = 512,
                dim_latent = 512,
                num_text_tokens = 49408,
                text_enc_depth = 6,
                text_seq_len = 256,
                text_heads = 8,
                use_mlm = True,
                visual_ssl = visual_ssl,           # SSL module passed into CLIP
                use_all_token_embeds = False,
                extra_latent_projection = False,
                mlm_random_token_prob = 0.1
            )
        else:
            enc = timm.create_model(model_name, pretrained=True).to(device=device) if pretrained_image else None
            if enc:
                enc = nn.Sequential(*list(enc.children())[:-1])
            model = XCLIP(
                image_encoder = enc,
                dim_image = 512,           # must be set as the same dimensions as the vision transformer above
                dim_text = 512,
                dim_latent = 512,
                num_text_tokens = 49408,
                text_enc_depth = 6,
                text_seq_len = 256,
                text_heads = 8,
                text_has_cls_token = True,
                visual_has_cls_token = True,
                use_all_token_embeds = filip,           # whether to use fine-grained contrastive learning (FILIP)
                decoupled_contrastive_learning = dcl,  # use decoupled contrastive learning (DCL) objective function, removing positive pairs from the denominator of the InfoNCE loss (CLOOB + DCL)
                extra_latent_projection = elp,         # whether to use separate projections for text-to-image vs image-to-text comparisons (CLOOB)
                use_visual_ssl = False,             # whether to do self supervised learning on iages
                use_mlm = mlm,                        # use masked language learning (MLM) on text (DeCLIP)
                #TODO: input correct vals here
                text_ssl_loss_weight = 0.05,            # weight for text MLM loss
                image_ssl_loss_weight = 0.05            # weight for image self-supervised learning loss
            )
        if precision == "amp" or precision == "fp32":
            model = model.float()
        if precision == "fp16":
            assert device.type != 'cpu', "CPU training is not supported for fp16"
            convert_weights_to_fp16(model)
        model.to(device=device)
        return model
    elif simclr:
        enc = timm.create_model(model_name, num_classes=0).to(device=device)
        # enc = nn.Sequential(*list(enc.children())[:-1])
        #TODO: check these settings
        mlp = build_mlp(in_dim=768, mlp_dim=2048, out_dim=1000).to(device=device)
        model = SIMCLR(
            vision_width = 768,
            vision_model = enc,
            build_mlp = mlp
        )
        if precision == "amp" or precision == "fp32":
            model = model.float()
        model.to(device=device)
        if precision == "fp16":
            assert device.type != 'cpu', "CPU training is not supported for fp16"
            convert_weights_to_fp16(model)
        return model
    elif model_name == "coca":
        enc = timm.create_model('vit_large_patch16_224', pretrained=True).to(device=device)
        enc = nn.Sequential(*list(enc.children())[:-1])
        model = CoCa(
            dim = 512,                     # model dimension
            img_encoder = enc,             # vision transformer - image encoder, returning image embeddings as (batch, seq, dim)
            image_dim = 1024,              # image embedding dimension, if not the same as model dimensions
            num_tokens = 49408,            # number of text tokens
            unimodal_depth = 6,            # depth of the unimodal transformer
            multimodal_depth = 6,          # depth of the multimodal transformer
            dim_head = 64,                 # dimension per attention head
            heads = 8,                     # number of attention heads
            caption_loss_weight = .5,      # weight on the autoregressive caption loss
            contrastive_loss_weight = .4,  # weight on the contrastive loss between image and text CLS embeddings
        )
        if precision == "amp" or precision == "fp32":
            model = model.float()
        if precision == "fp16":
            assert device.type != 'cpu', "CPU training is not supported for fp16"
            convert_weights_to_fp16(model)
        model.to(device=device)
        return model
    #SIMCLR
    #https://dl.fbaipublicfiles.com/slip/simclr_base_25ep.pt
    
    model_name = model_name.replace('/', '-')  # for callers using old naming with / in ViT names
    if pretrained.lower() == 'openai':
        logging.info(f'Loading pretrained {model_name} from OpenAI.')
        model = load_openai_model(model_name, device=device, jit=jit, cache_dir=cache_dir)
        # See https://discuss.pytorch.org/t/valueerror-attemting-to-unscale-fp16-gradients/81372
        if precision == "amp" or precision == "fp32":
            model = model.float()
    else:
        if model_name in _MODEL_CONFIGS:
            logging.info(f'Loading {model_name} model config.')
            model_cfg = deepcopy(_MODEL_CONFIGS[model_name])
        else:
            logging.error(f'Model config for {model_name} not found; available models {list_models()}.')
            raise RuntimeError(f'Model config for {model_name} not found.')

        if force_quick_gelu:
            # override for use of QuickGELU on non-OpenAI transformer models
            model_cfg["quick_gelu"] = True

        if pretrained_image:
            if 'timm_model_name' in model_cfg.get('vision_cfg', {}):
                # pretrained weight loading for timm models set via vision_cfg
                model_cfg['vision_cfg']['timm_model_pretrained'] = True
            else:
                assert False, 'pretrained image towers currently only supported for timm models'
        if model_cfg.get('text_cfg', {}) != {}:
            model = CLIP(**model_cfg)
        else:
            model = VisionModel(**model_cfg)
        pretrained_cfg = {}
        if pretrained:
            checkpoint_path = ''
            pretrained_cfg = get_pretrained_cfg(model_name, pretrained)
            if pretrained_cfg:
                checkpoint_path = download_pretrained(pretrained_cfg, cache_dir=cache_dir)
            elif os.path.exists(pretrained):
                checkpoint_path = pretrained

            if checkpoint_path:
                logging.info(f'Loading pretrained {model_name} weights ({pretrained}).')
                load_checkpoint(model, checkpoint_path)
                
            else:
                logging.warning(f'Pretrained weights ({pretrained}) not found for model {model_name}.')
                raise RuntimeError(f'Pretrained weights ({pretrained}) not found for model {model_name}.')        
        model.to(device=device)
        if precision == "fp16":
            assert device.type != 'cpu', "CPU training is not supported for fp16"
            convert_weights_to_fp16(model)

        # set image / mean metadata from pretrained_cfg if available, or use default
        model.visual.image_mean = pretrained_cfg.get('mean', None) or OPENAI_DATASET_MEAN
        model.visual.image_std = pretrained_cfg.get('std', None) or OPENAI_DATASET_STD

        if jit:
            model = torch.jit.script(model)

    return model

def init_weights_vit_jax(module: nn.Module, name: str = '', head_bias: float = 0.):
    """ ViT weight initialization, matching JAX (Flax) impl """
    if isinstance(module, nn.Linear):
        if name.startswith('head'):
            nn.init.zeros_(module.weight)
            nn.init.constant_(module.bias, head_bias)
        else:
            nn.init.xavier_uniform_(module.weight)
            if module.bias is not None:
                nn.init.normal_(module.bias, std=1e-6) if 'mlp' in name else nn.init.zeros_(module.bias)
    elif isinstance(module, nn.Conv2d):
        lecun_normal_(module.weight)
        if module.bias is not None:
            nn.init.zeros_(module.bias)
    elif hasattr(module, 'init_weights'):
        module.init_weights()

def apply_random_weights_skipping_first_k_layers_vit(model, k):
    i = 0
    sequentials = []
    for idxch, child in enumerate(model.children()):
        print("Model child number {} is {} \n".format(idxch, type(child)))
        if isinstance(child, torch.nn.modules.container.Sequential):
          sequentials.append(child)
    print("This method will randomize weights of all Conv2D, Block and Linear layers after the first {} layers, in all sequentials \n".format(k))
    print("There are {} sequentials \n".format(len(sequentials)))
    for sequential in sequentials:
        for child in sequential.children():
          print("Sequential child number {} is {} \n".format(i, type(child)))
          if i <= k:
              i += 1
              continue
          if isinstance(child, nn.Linear) or isinstance(child, nn.Conv2d):
              child.weight.data = torch.randn(child.weight.size())
              if child.bias is not None:
                  child.bias.data = torch.randn(child.bias.size())
          #timm vit blocks
          if isinstance(child, Block):
              child.attn.qkv.weight.data = torch.randn(child.attn.qkv.weight.size())
              child.attn.proj.weight.data = torch.randn(child.attn.proj.weight.size())
              child.mlp.fc1.weight.data = torch.randn(child.mlp.fc1.weight.size())
              child.mlp.fc2.weight.data = torch.randn(child.mlp.fc2.weight.size())
          i += 1

def get_bioclip_preprocess():
    #####PUT YOUR OWN PATH IN HERE
    with open("/home/km3888/open_clip/transform.pkl", "rb") as f:
        loaded_transforms = pickle.load(f)
    loaded_transform = transforms.Compose(loaded_transforms)
    return loaded_transform

def create_model_and_transforms(
        model_name: str,
        pretrained: str = '',
        precision: str = 'fp32',
        device: torch.device = torch.device('cpu'),
        jit: bool = False,
        force_quick_gelu: bool = False,
        pretrained_image: bool = False,
        image_filip: bool = False,
        dcl: bool = False,
        elp: bool = False,
        vssl: bool = False,
        mlm: bool = False,
        image_simclr: bool = False,
        simclr_trans: bool = False,
        grayscale: bool = False,
        downsample_trans: bool = False,
        augreg_trans: bool = False,
        imsize: int = 224,
        cache_dir: Optional[str] = None,
        image_mean = None,
        image_std = None,
):
    if pretrained=='bioclip':
        model = load_openai_model(model_name, device=device, jit=jit, cache_dir=cache_dir)
        ###########PUT YOUR OWN PATH IN HERE #############
        # Reason for this code is that BioCLIP makes their model available through open_clip API
        # VLHub already has a submodule called "open_clip" which makes it difficult to import the model
        # Instead we load the model under a different python process and save the model + transform so
        # that we can load them with torch.load()
        state_dict = torch.load("/vast/km3888/arbor_evals/bioclip.pth")
        model.load_state_dict(state_dict)
        preprocess = get_bioclip_preprocess()
        if precision == "amp" or precision == "fp32":
            model = model.float()
        return model, preprocess, preprocess

    model = create_model(
    model_name, pretrained, precision, device, jit,
    force_quick_gelu=force_quick_gelu,
    pretrained_image=pretrained_image, filip=image_filip, 
    dcl=dcl, elp=elp, vssl=vssl, mlm=mlm, imsize=imsize, 
    simclr=image_simclr, cache_dir=cache_dir
    )
    #FIXME hardcoded size
    image_mean = image_mean or getattr(model.visual, 'image_mean', None)
    image_std = image_std or getattr(model.visual, 'image_std', None)
    if model_name == "coca" or image_simclr:
        preprocess_train = image_transform(224, is_train=True, mean=image_mean, std=image_std, simclr_trans=simclr_trans, grayscale=grayscale, downsample_trans=downsample_trans, augreg_trans=augreg_trans)
        preprocess_val = image_transform(224, is_train=False, mean=image_mean, std=image_std, simclr_trans=simclr_trans, downsample_trans=downsample_trans, augreg_trans=augreg_trans)
    else:
        preprocess_train = image_transform(imsize, is_train=True, mean=image_mean, std=image_std, simclr_trans=simclr_trans, grayscale=grayscale, downsample_trans=downsample_trans, augreg_trans=augreg_trans)
        preprocess_val = image_transform(imsize, is_train=False, mean=image_mean, std=image_std, simclr_trans=simclr_trans, downsample_trans=downsample_trans, augreg_trans=augreg_trans)
    return model, preprocess_train, preprocess_val

def list_models():
    """ enumerate available model architectures based on config files """
    return list(_MODEL_CONFIGS.keys())


def add_model_config(path):
    """ add model config path or file and update registry """
    if not isinstance(path, Path):
        path = Path(path)
    _MODEL_CONFIG_PATHS.append(path)
    _rescan_model_configs()
