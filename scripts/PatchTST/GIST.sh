#!/bin/bash

DATE=$(date +%y%m%d%H)
model_name=PatchTST
model_id=$DATE

if [ ! -d "./logs/$model_id" ]; then
    mkdir -p ./logs/$model_id
fi

seq_len=336

root_path_name=./data/GIST_dataset/
data_path_name=GIST_sisuldong.csv
data_name=GIST

random_seed=2021

#for pred_len in 1 2 4 8 16
for pred_len in 1 2
do
    if [ $pred_len -eq 1 ]; then
        label_len=0
    else
        label_len=$((pred_len/2))
    fi
    python -u run_longExp.py \
      --gpu 0 \
      --random_seed $random_seed \
      --is_training 1 \
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
      --itr 1 --batch_size 128 --learning_rate 0.0001 >logs/$model_id/$model_name'_'$data_name'_'$seq_len'_'$pred_len.log
done