import subprocess
from tqdm.auto import tqdm
import os
import pandas as pd

def image_size_set(model_name, df):
    row = df[df['updated_name'] == model_name]
    if not row.empty:
        imsize = int(row.iloc[0]['image_size'])
        if imsize:
            return imsize
    if "384" in model_name:
        image_size = 384
    elif "512" in model_name:
        image_size = 512
    elif "256" in model_name:
        image_size = 256
    elif "336" in model_name:
        image_size = 336
    elif "280" in model_name:
        image_size = 280
    elif "475" in model_name:
        image_size = 475
    elif "448" in model_name:
        image_size = 448
    else:
        image_size = 224
    return image_size

models = [
 'repvgg_a2',
 'repvgg_b0',
 'repvgg_b1',
 'repvgg_b1g4',
 'repvgg_b2',
 'repvgg_b2g4',
 'repvgg_b3',
 'repvgg_b3g4',
 'res2net101_26w_4s',
 'res2net50_14w_8s',
 'res2net50_26w_4s',
 'res2net50_26w_6s',
 'res2net50_26w_8s',
 'res2net50_48w_2s',
 'res2next50',
 'resmlp_12_224',
 'resmlp_12_distilled_224',
 'resmlp_24_224',
 'resmlp_24_distilled_224',
 'resmlp_36_224',
 'resmlp_36_distilled_224',
 'resmlp_big_24_distilled_224',
 'resnest101e',
 'resnest14d',
 'resnest200e',
 'resnest269e',
 'resnest26d',
 'resnest50d',
 'resnest50d_1s4x24d',
 'resnest50d_4s2x40d',
 'resnet101',
 'resnet101d',
 'resnet10t',
 'resnet14t',
 'resnet152',
 'resnet152',
 'resnet152d',
 'resnet101.a1_in1k',
 'resnet101.a1h_in1k',
 'resnet101.a2_in1k',
 'resnet101.a3_in1k',
 'resnet101.gluon_in1k',
 'resnet101.tv2_in1k',
 'resnet101.tv_in1k',
 'resnet101c.gluon_in1k',
 'resnet101d.gluon_in1k',
 'resnet101d.ra2_in1k',
 'resnet101s.gluon_in1k',
 'resnet10t.c3_in1k',
 'resnet14t.c3_in1k',
 'resnet152.a1_in1k',
 'resnet152.a1h_in1k',
 'resnet152.a2_in1k',
 'resnet152.a3_in1k',
 'resnet152.gluon_in1k',
 'resnet152.tv2_in1k',
 'resnet152.tv_in1k',
 'resnet152c.gluon_in1k',
 'resnet152d.gluon_in1k',
 'resnet152d.ra2_in1k',
 'resnet152s.gluon_in1k',
 'resnet18.a1_in1k',
 'resnet18.a2_in1k',
 'resnet18.a3_in1k',
 'resnet18.fb_ssl_yfcc100m_ft_in1k',
 'resnet18.fb_swsl_ig1b_ft_in1k',
 'resnet18.gluon_in1k',
 'resnet18.tv_in1k',
 'resnet18d.ra2_in1k',
 'resnet200.untrained',
 'resnet200d.ra2_in1k',
 'resnet26.bt_in1k',
 'resnet26d.bt_in1k',
 'resnet26t.ra2_in1k',
 'resnet34.a1_in1k',
 'resnet34.a2_in1k',
 'resnet34.a3_in1k',
 'resnet34.bt_in1k',
 'resnet34.gluon_in1k',
 'resnet34.tv_in1k',
 'resnet34d.ra2_in1k',
 'resnet50.a1_in1k',
 'resnet50.a1h_in1k',
 'resnet50.a2_in1k',
 'resnet50.a3_in1k',
 'resnet50.am_in1k',
 'resnet50.b1k_in1k',
 'resnet50.b2k_in1k',
 'resnet50.bt_in1k',
 'resnet50.c1_in1k',
 'resnet50.c2_in1k',
 'resnet50.d_in1k',
 'resnet50.fb_ssl_yfcc100m_ft_in1k',
 'resnet50.fb_swsl_ig1b_ft_in1k',
 'resnet50.gluon_in1k',
 'resnet50.ra_in1k',
 'resnet50.ram_in1k',
 'resnet50.tv2_in1k',
 'resnet50.tv_in1k',
 'resnet50_gn.a1h_in1k',
 'resnet50c.gluon_in1k',
 'resnet50d.a1_in1k',
 'resnet50d.a2_in1k',
 'resnet50d.a3_in1k',
 'resnet50d.gluon_in1k',
 'resnet50d.ra2_in1k',
 'resnet50s.gluon_in1k',
 'resnet50t.untrained',
 'resnetaa101d.sw_in12k',
 'resnetaa101d.sw_in12k_ft_in1k',
 'resnetaa50.a1h_in1k',
 'resnetaa50d.d_in12k',
 'resnetaa50d.sw_in12k',
 'resnetaa50d.sw_in12k_ft_in1k',
 'resnetblur101d.untrained',
 'resnetblur18.untrained',
 'resnetblur50.bt_in1k',
 'resnetblur50d.untrained',
 'resnetrs101.tf_in1k',
 'resnetrs152.tf_in1k',
 'resnetrs200.tf_in1k',
 'resnetrs270.tf_in1k',
 'resnetrs350.tf_in1k',
 'resnetrs420.tf_in1k',
 'resnetrs50.tf_in1k',
 'resnext101_32x16d.fb_ssl_yfcc100m_ft_in1k',
 'resnext101_32x16d.fb_swsl_ig1b_ft_in1k',
 'resnext101_32x16d.fb_wsl_ig1b_ft_in1k',
 'resnext101_32x32d.fb_wsl_ig1b_ft_in1k',
 'resnext101_32x48d.fb_wsl_ig1b_ft_in1k',
 'resnext101_32x4d.fb_ssl_yfcc100m_ft_in1k',
 'resnext101_32x4d.fb_swsl_ig1b_ft_in1k',
 'resnext101_32x4d.gluon_in1k',
 'resnext101_32x4d.untrained',
 'resnext101_32x8d.fb_ssl_yfcc100m_ft_in1k',
 'resnext101_32x8d.fb_swsl_ig1b_ft_in1k',
 'resnext101_32x8d.fb_wsl_ig1b_ft_in1k',
 'resnext101_32x8d.tv2_in1k',
 'resnext101_32x8d.tv_in1k',
 'resnext101_64x4d.c1_in1k',
 'resnext101_64x4d.gluon_in1k',
 'resnext101_64x4d.tv_in1k',
 'resnext50_32x4d.a1_in1k',
 'resnext50_32x4d.a1h_in1k',
 'resnext50_32x4d.a2_in1k',
 'resnext50_32x4d.a3_in1k',
 'resnext50_32x4d.fb_ssl_yfcc100m_ft_in1k',
 'resnext50_32x4d.fb_swsl_ig1b_ft_in1k',
 'resnext50_32x4d.gluon_in1k',
 'resnext50_32x4d.ra_in1k',
 'resnext50_32x4d.tv2_in1k',
 'resnext50_32x4d.tv_in1k',
 'resnext50d_32x4d.bt_in1k'
 'resnetv2_101',
 'resnetv2_101x1_bitm',
 'resnetv2_101x3_bitm',
 'resnetv2_152x2_bit_teacher',
 'resnetv2_152x2_bit_teacher_384',
 'resnetv2_152x2_bitm',
 'resnetv2_152x4_bitm',
 'resnetv2_50',
 'resnetv2_50d_evos',
 'resnetv2_50d_gn',
 'resnetv2_50x1_bit_distilled',
 'resnetv2_50x1_bitm',
 'resnetv2_50x3_bitm',
 'rexnet_100',
 'rexnet_130',
 'rexnet_150',
 'rexnet_200',
 'sebotnet33ts_256',
 'sehalonet33ts',
 'selecsls42b',
 'selecsls60',
 'selecsls60b',
 'semnasnet_075.rmsp_in1k',
 'semnasnet_100.rmsp_in1k',
 'sequencer2d_l',
 'sequencer2d_m',
 'sequencer2d_s',
 'seresnet152d.ra2_in1k',
 'seresnet33ts',
 'seresnet50.a1_in1k',
 'seresnet50.a2_in1k',
 'seresnet50.a3_in1k',
 'seresnet50.ra2_in1k',
 'seresnext101_32x4d.gluon_in1k',
 'seresnext101_32x8d.ah_in1k',
 'seresnext101_64x4d.gluon_in1k',
 'seresnext101d_32x8d.ah_in1k',
 'seresnext26d_32x4d.bt_in1k',
 'seresnext26t_32x4d.bt_in1k',
 'seresnext50_32x4d.gluon_in1k',
 'seresnext50_32x4d.racm_in1k',
 'seresnextaa101d_32x8d.ah_in1k',
 'seresnextaa101d_32x8d.sw_in12k',
 'seresnextaa101d_32x8d.sw_in12k_ft_in1k',
 'seresnextaa101d_32x8d.sw_in12k_ft_in1k_288',
 'skresnet18',
 'skresnet34',
 'skresnext50_32x4d',
 'spnasnet_100.rmsp_in1k',
 'ssl_resnet18',
 'ssl_resnet50',
 'ssl_resnext101_32x16d',
 'ssl_resnext101_32x4d',
 'ssl_resnext101_32x8d',
 'ssl_resnext50_32x4d',
 'swin_base_patch4_window12_384',
 'swin_base_patch4_window7_224',
 'swin_large_patch4_window12_384',
 'swin_large_patch4_window7_224',
 'swin_s3_base_224',
 'swin_s3_small_224',
 'swin_s3_tiny_224',
 'swin_small_patch4_window7_224',
 'swin_tiny_patch4_window7_224',
 'swinv2_base_window12to16_192to256_22kft1k',
 'swinv2_base_window12to24_192to384_22kft1k',
 'swinv2_base_window16_256',
 'swinv2_base_window8_256',
 'swinv2_cr_small_224',
 'swinv2_cr_small_ns_224',
 'swinv2_cr_tiny_ns_224',
 'swinv2_large_window12to16_192to256_22kft1k',
 'swinv2_large_window12to24_192to384_22kft1k',
 'swinv2_small_window16_256',
 'swinv2_small_window8_256',
 'swinv2_tiny_window16_256',
 'swinv2_tiny_window8_256',
 'swsl_resnet18',
 'swsl_resnet50',
 'swsl_resnext101_32x16d',
 'swsl_resnext101_32x4d',
 'swsl_resnext101_32x8d',
 'swsl_resnext50_32x4d',
 'tf_efficientnet_b0.aa_in1k',
 'tf_efficientnet_b1.aa_in1k',
 'tf_efficientnet_b2.aa_in1k',
 'tf_efficientnet_b3.aa_in1k',
 'tf_efficientnet_b4.aa_in1k',
 'tf_efficientnet_b5.ra_in1k',
 'tf_efficientnet_b6.aa_in1k',
 'tf_efficientnet_b7.ra_in1k',
 'tf_efficientnet_b8.ap_in1k',
 'tf_efficientnet_cc_b0_4e.in1k',
 'tf_efficientnet_cc_b0_8e.in1k',
 'tf_efficientnet_cc_b1_8e.in1k',
 'tf_efficientnet_el.in1k',
 'tf_efficientnet_em.in1k',
 'tf_efficientnet_es.in1k',
 'tf_efficientnet_l2_ns',
 'tf_efficientnet_lite0.in1k',
 'tf_efficientnet_lite1.in1k',
 'tf_efficientnet_lite2.in1k',
 'tf_efficientnet_lite3.in1k',
 'tf_efficientnet_lite4.in1k',
 'tf_efficientnetv2_b0.in1k',
 'tf_efficientnetv2_b1.in1k',
 'tf_efficientnetv2_b2.in1k',
 'tf_efficientnetv2_b3.in1k',
 'tf_efficientnetv2_l.in1k',
 'tf_efficientnetv2_l.in21k_ft_in1k',
 'tf_efficientnetv2_m.in1k',
 'tf_efficientnetv2_m.in21k_ft_in1k',
 'tf_efficientnetv2_s.in1k',
 'tf_efficientnetv2_s.in21k_ft_in1k',
 'tf_efficientnetv2_xl.in21k_ft_in1k',
 'tf_inception_v3',
 'tf_mixnet_l.in1k',
 'tf_mixnet_m.in1k',
 'tf_mixnet_s.in1k',
 'tf_mobilenetv3_large_075.in1k',
 'tf_mobilenetv3_large_100.in1k',
 'tf_mobilenetv3_large_minimal_100.in1k',
 'tf_mobilenetv3_small_075.in1k',
 'tf_mobilenetv3_small_100.in1k',
 'tf_mobilenetv3_small_minimal_100.in1k',
 'tinynet_a.in1k',
 'tinynet_b.in1k',
 'tinynet_c.in1k',
 'tinynet_d.in1k',
 'tinynet_e.in1k',
 'tnt_s_patch16_224',
 'tv_densenet121',
 'tv_resnet101',
 'tv_resnet152',
 'tv_resnet34',
 'tv_resnet50',
 'tv_resnext50_32x4d',
 'twins_pcpvt_base',
 'twins_pcpvt_large',
 'twins_pcpvt_small',
 'twins_svt_base',
 'twins_svt_large',
 'twins_svt_small',
 'vgg11',
 'vgg11_bn',
 'vgg13',
 'vgg13_bn',
 'vgg16',
 'vgg16_bn',
 'vgg19',
 'vgg19_bn',
 'visformer_small',
 'volo_d1_224',
 'volo_d1_384',
 'volo_d2_224',
 'volo_d2_384',
 'volo_d3_224',
 'volo_d3_448',
 'volo_d4_224',
 'volo_d4_448',
 'volo_d5_224',
 'volo_d5_448',
 'volo_d5_512',
 'wide_resnet101_2',
 'wide_resnet50_2',
 'wide_resnet50_2',
 'xception',
 'xception41',
 'xception41p',
 'xception65',
 'xception65p',
 'xception71',
 'xcit_large_24_p16_224',
 'xcit_large_24_p16_224_dist',
 'xcit_large_24_p16_384_dist',
 'xcit_large_24_p8_224',
 'xcit_large_24_p8_224_dist',
 'xcit_large_24_p8_384_dist',
 'xcit_medium_24_p16_224',
 'xcit_medium_24_p16_224_dist',
 'xcit_medium_24_p16_384_dist',
 'xcit_medium_24_p8_224',
 'xcit_medium_24_p8_224_dist',
 'xcit_medium_24_p8_384_dist',
 'xcit_nano_12_p16_224',
 'xcit_nano_12_p16_224_dist',
 'xcit_nano_12_p16_384_dist',
 'xcit_nano_12_p8_224',
 'xcit_nano_12_p8_224_dist',
 'xcit_nano_12_p8_384_dist',
 'xcit_small_12_p16_224',
 'xcit_small_12_p16_224_dist',
 'xcit_small_12_p16_384_dist',
 'xcit_small_12_p8_224',
 'xcit_small_12_p8_224_dist',
 'xcit_small_12_p8_384_dist',
 'xcit_small_24_p16_224',
 'xcit_small_24_p16_224_dist',
 'xcit_small_24_p16_384_dist',
 'xcit_small_24_p8_224',
 'xcit_small_24_p8_224_dist',
 'xcit_small_24_p8_384_dist',
 'xcit_tiny_12_p16_224',
 'xcit_tiny_12_p16_224_dist',
 'xcit_tiny_12_p16_384_dist',
 'xcit_tiny_12_p8_224',
 'xcit_tiny_12_p8_224_dist',
 'xcit_tiny_12_p8_384_dist',
 'xcit_tiny_24_p16_224',
 'xcit_tiny_24_p16_224_dist',
 'xcit_tiny_24_p16_384_dist',
 'xcit_tiny_24_p8_224',
 'xcit_tiny_24_p8_224_dist',
 'xcit_tiny_24_p8_384_dist',
 ]

df_is = pd.read_csv("/scratch/bf996/vlhub/metadata/meta-analysis-results.csv")

caption_subsets = ["--caption-subset=in100", "--caption-subset=in100_dogs", ""]

save_csv = "/scratch/bf996/vlhub/logs/imagenet_timm_sweep.csv"

increment = 0

while os.path.exists(save_csv):
    increment += 1
    save_csv = "/scratch/bf996/vlhub/logs/imagenet_timm_sweep_{}.csv".format(increment)

script_path = 'python src/training/main.py --batch-size=128 --workers=8 --imagenet-val "/imagenet/val/" --imagenet-v2 "/scratch/bf996/datasets" --imagenet-s "/imagenet-sketch" --imagenet-a "/imagenet-a" --imagenet-r "/imagenet-r" --model={} --zeroshot-frequency=1 --linear-probe=True {} --image-size={} --save-results-to-csv={};'

pythonpath_cmd = 'export PYTHONPATH="$PYTHONPATH:/scratch/bf996/vlhub/src"'

subprocess.run(pythonpath_cmd, shell=True)

for idx, model in tqdm(enumerate(models)):
    for subset in caption_subsets:
        image_size = str(image_size_set(model, df_is))
        command = script_path.format(model, subset, image_size, save_csv)
        try:
            subprocess.run(command, shell=True)
        except Exception as e:
            print(e)
            continue