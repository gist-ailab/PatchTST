#!/bin/bash

DATE=$(date +%y%m%d%H)
model_name=PatchTST
model_id=$DATE
exp_id="${DATE}_Pretrain_GIST_infer_$model_name"

if [ ! -d "./logs/$exp_id" ]; then
    mkdir -p ./logs/$exp_id
fi

seq_len=256
label_len=0

# root_path_name=/home/intern/doyoon/innovation/PatchTST/data/Germany_Household_Data/preprocessed
root_path_name=/home/seongho_bak/Projects/PatchTST/data/GIST_dataset/converted
data_path_name='type=all'
data_name=GIST
random_seed=2024
e_layers=4


export CUDA_VISIBLE_DEVICES=2

for pred_len in 16 # 8 4 2 1  
do
    python -u run_longExp.py \
      --gpu 0 \
      --use_amp \
      --individual 1 \
      --random_seed $random_seed \
      --is_pretraining 1 \
      --is_inference 1 \
      --checkpoints /home/seongho_bak/Projects/PatchTST/checkpoints/24110403_PatchTST_GIST_ftMS_sl256_ll0_pl16_dm256_nh8_el4_dl1_df512_fc1_ebtimeF_dtTrue_Exp_0/checkpoint.pth\
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
      --e_layers $e_layers \
      --n_heads 8 \
      --d_model 256 \
      --d_ff 512 \
      --dropout 0.05\
      --fc_dropout 0.05\
      --head_dropout 0\
      --patch_len 16\
      --stride 8\
      --des 'pretrain' \
      --train_epochs 100\
      --patience 20\
      --embed 'timeF' \
      --itr 1 --batch_size 16 --learning_rate 0.0001 >logs/$exp_id/$model_name'_'$data_name'_'$seq_len'_'$pred_len'_'$e_layers.log
done