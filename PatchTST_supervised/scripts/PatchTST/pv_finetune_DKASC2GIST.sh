if [ ! -d "./logs" ]; then
    mkdir ./logs
fi
exp_id='231229_A1toG_01'

if [ ! -d "./logs/$exp_id" ]; then
    mkdir ./logs/$exp_id
fi

seq_len=336
model_name=PatchTST

root_path_name=./dataset/GIST/
data_path_name=sisuldong.csv
model_id_name=pv_GIST_$exp_id'_'
data_name=pv_GIST

random_seed=2021
# for pred_len in 96 192 336 720
# for pred_len in 24 48 96 192
for pred_len in 96
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
      --e_layers 3 \
      --n_heads 16 \
      --d_model 128 \
      --d_ff 256 \
      --dropout 0.2\
      --fc_dropout 0.2\
      --head_dropout 0\
      --patch_len 16\
      --stride 8\
      --des 'Exp' \
      --train_epochs 100\
      --patience 20\
      --embed 'timeF' \
      --exp_id $exp_id \
      --resume  \
      --itr 1 --batch_size 128 --learning_rate 0.0001 >logs/$exp_id/GIST_$exp_id'_'$model_name'_'$model_id_name'_'$seq_len'_'$pred_len.log 
done