if [ ! -d "./logs" ]; then
    mkdir ./logs
fi
model_id_name='240328_1A'

if [ ! -d "./logs/$model_id_name" ]; then
    mkdir ./logs/$model_id_name
fi

seq_len=24
model_name=Arima

root_path_name=./dataset/DKASC/
data_path_name='91-Site_DKA-M9_B-Phase.csv'
data_name=pv_DKASC

random_seed=2021
for pred_len in 1 2 3 4
do
    python -u run_longExp.py \
        --gpu 0 \
        --random_seed $random_seed \
        --is_training 1 \
        --root_path $root_path_name \
        --data_path $data_path_name \
        --model_id $model_id_name'_'$seq_len'_'$pred_len \
        --model $model_name \
        --data $data_name \
        --features M \
        --seq_len $seq_len \
        --pred_len $pred_len \
        --enc_in 21 \
        --des 'Exp' \
        --train_epochs 100\
        --patience 20\
        --embed 'timeF' \
        --exp_id $model_id_name \
        --itr 1 --batch_size 16  >logs/$model_id_name/$model_name'_'$model_id_name'_'$seq_len'_'$pred_len.log 
done