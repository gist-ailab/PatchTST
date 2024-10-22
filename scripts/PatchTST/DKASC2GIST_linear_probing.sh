#!/bin/bash

DATE=$(date +%y%m%d%H)
model_name=PatchTST
model_id=$DATE
exp_id="${DATE}_Linear_Probing_DKASC2GIST_$model_name"

if [ ! -d "./logs/$exp_id" ]; then
    mkdir -p ./logs/$exp_id
fi

seq_len=336
label_len=0

root_path_name=/ailab_mat/dataset/PV/GIST_dataset/converted
data_path_name='type=all'
data_name=GIST
random_seed=2024


export CUDA_VISIBLE_DEVICES=4


for pred_len in 24 #1 2 4 8 16
do
    python -u run_finetune.py \
      --gpu 0 \
      --use_amp \
      --random_seed $random_seed \
      --is_training 1 \
      --is_linear_probe 1 \
      --checkpoints  /SSDe/sowon_choi/PatchTST/checkpoints/24102105_PatchTST_DKASC_ftMS_sl336_ll0_pl24_dm128_nh16_el5_dl1_df1024_fc1_ebtimeF_dtTrue_Exp_0/checkpoint.pth \
      --root_path $root_path_name \
      --data_path $data_path_name \
      --model_id $model_id \
      --model $model_name \
      --data $data_name \
      --features MS \
      --seq_len $seq_len \
      --label_len $label_len \
      --pred_len $pred_len \
      --enc_in 5 \
      --e_layers 5 \
      --n_heads 16 \
      --d_model 128 \
      --d_ff 1024 \
      --dropout 0.05\
      --fc_dropout 0.05\
      --head_dropout 0\
      --patch_len 16\
      --stride 8\
      --des 'Exp' \
      --train_epochs 100\
      --patience 20\
      --embed 'timeF' \
      --itr 1 --batch_size 512 --learning_rate 0.001 >logs/$exp_id/$model_name'_'$data_name'_'$seq_len'_'$pred_len.log
done