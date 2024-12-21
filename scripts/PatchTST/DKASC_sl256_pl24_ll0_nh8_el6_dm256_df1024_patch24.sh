#!/bin/bash

DATE=$(date +%y%m%d%H)
model_name=PatchTST
model_id=$DATE
exp_id="${DATE}_Pretrain_DKASC_$model_name"

if [ ! -d "./logs/$exp_id" ]; then
    mkdir -p ./logs/$exp_id
fi

root_path_name="/ailab_mat/dataset/PV/DKASC/processed_data_all/"
data_name=DKASC
random_seed=2024

seq_len=240
pred_len=24
label_len=0

n_heads=8
e_layers=6
d_model=256
d_ff=1024
patch_len=24

local_rank=0
export CUDA_VISIBLE_DEVICES=0,1
export WORLD_SIZE=2 # 총 프로세스 수
export MASTER_ADDR='localhost'
# export MASTER_PORT='12356'  # 임의의 빈 포트
export MASTER_PORT=12356  # 임의의 빈 포트

# CPU 코어 개수와 num_workers 계산
total_cores=$(nproc)  # 전체 CPU 코어 개수
num_workers=$((total_cores / 2))  # num_workers = CPU 코어 수 // 2
if [ "$num_workers" -lt 1 ]; then
    num_workers=1
fi

setting_name="${model_name}_sl${seq_len}_pl${pred_len}_ll${label_len}_nh${n_heads}_el${e_layers}_dm${d_model}_df${d_ff}_patch${patch_len}"

echo "Total CPU cores: $total_cores"
echo "Using num_workers: $num_workers"
echo "Generated setting name: $setting_name"

# 환경 변수 출력
echo "Environment variables before torchrun:"
echo "LOCAL_RANK: $LOCAL_RANK"
echo "RANK: $RANK"
echo "WORLD_SIZE: $WORLD_SIZE"
echo "MASTER_ADDR: $MASTER_ADDR"
echo "MASTER_PORT: $MASTER_PORT"

for pred_len in 24
do
    torchrun --nproc_per_node=$WORLD_SIZE --master_port=$MASTER_PORT run_longExp.py \
        --random_seed $random_seed \
        --is_pretraining 1 \
        --model_id $model_id \
        --model $model_name \
        --data $data_name \
        --root_path $root_path_name \
        --checkpoints "${SCRIPT_NAME}_${seq_len}_${pred_len}" \
        --seq_len $seq_len\
        --label_len $label_len \
        --pred_len $pred_len\
        --fc_dropout 0.05\
        --head_dropout 0\
        --patch_len $patch_len\
        --individual 1 \
        --enc_in 5 \
        --d_model $d_model \
        --n_heads $n_heads \
        --e_layers $e_layers \
        --d_ff $d_ff \
        --dropout 0.05\
        --embed 'timeF' \
        --num_workers $num_workers \
        --batch_size 256 \
        --learning_rate 0.0001 \
        --gpu 0 \
        --des 'Exp' \
        --distributed >logs/$exp_id/$model_name'_'$data_name'_'$seq_len'_'$pred_len'_'$n_heads'_'$patch_len.log
done