#!/bin/bash

DATE=$(date +%y%m%d%H)
model_name=PatchTST
model_id=$DATE
exp_id="${DATE}_Fully_finetune_OEDI_Georgia_$model_name"

if [ ! -d "./logs/$exp_id" ]; then
    mkdir -p ./logs/$exp_id
fi

seq_len=256
label_len=0

# root_path_name=/home/intern/doyoon/innovation/PatchTST/data/OEDI/9069\(Georgia\)/preprocessed
root_path_name=data/OEDI/9069\(Georgia\)/preprocessed
data_path_name='type=all'
data_name=OEDI_Georgia
random_seed=2024

pred_len=(16)
checkponits=(
    "/ailab_mat/dataset/PV/checkpoints/24102218_PatchTST_DKASC_ftMS_sl256_ll0_pl16_dm128_nh16_el5_dl1_df1024_fc1_ebtimeF_dtTrue_Exp_0/checkpoint.pth"
    "/ailab_mat/dataset/PV/checkpoints/24102218_PatchTST_DKASC_ftMS_sl256_ll0_pl8_dm128_nh16_el5_dl1_df1024_fc1_ebtimeF_dtTrue_Exp_0/checkpoint.pth"
    "/ailab_mat/dataset/PV/checkpoints/24102218_PatchTST_DKASC_ftMS_sl256_ll0_pl4_dm128_nh16_el5_dl1_df1024_fc1_ebtimeF_dtTrue_Exp_0/checkpoint.pth"
    "/ailab_mat/dataset/PV/checkpoints/24102218_PatchTST_DKASC_ftMS_sl256_ll0_pl2_dm128_nh16_el5_dl1_df1024_fc1_ebtimeF_dtTrue_Exp_0/checkpoint.pth"
    "/ailab_mat/dataset/PV/checkpoints/24102218_PatchTST_DKASC_ftMS_sl256_ll0_pl1_dm128_nh16_el5_dl1_df1024_fc1_ebtimeF_dtTrue_Exp_0/checkpoint.pth"
)

export CUDA_VISIBLE_DEVICES=5
for i in "${!pred_len[@]}"; do
    pl=${pred_len[$i]}
    ckpt=${checkpoints[$i]}

    python -u run_longExp.py \
      --gpu 0 \
      --use_amp \
      --random_seed $random_seed \
      --individual 1 \
      --is_fully_finetune 1 \
      --checkpoints /home/seongho_bak/Projects/PatchTST/dkasc_ckpt/24110405_PatchTST_DKASC_AliceSprings_ftMS_sl256_ll0_pl16_dm256_nh8_el4_dl1_df512_fc1_ebtimeF_dtTrue_Exp_0/checkpoint.pth \
      --root_path $root_path_name \
      --data_path $data_path_name \
      --model_id $model_id \
      --model $model_name \
      --data $data_name \
      --features MS \
      --seq_len $seq_len \
      --label_len $label_len \
      --pred_len $pl \
      --enc_in 5 \
      --e_layers 4 \
      --n_heads 8 \
      --d_model 256 \
      --d_ff 512 \
      --dropout 0.05\
      --fc_dropout 0.05\
      --head_dropout 0\
      --patch_len 16\
      --stride 8\
      --des 'Exp' \
      --train_epochs 100\
      --patience 20\
      --embed 'timeF' \
      --itr 1 --batch_size 1024 --learning_rate 0.0001 >logs/$exp_id/$model_name'_'$data_name'_'$seq_len'_'$pl.log
done