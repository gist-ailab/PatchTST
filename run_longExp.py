import argparse
import os
import torch
from exp.exp_main import Exp_Main
import random
import numpy as np
import json
from utils.tools import StoreDictKeyPair 

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser(description='Autoformer & Transformer family for Time Series Forecasting')

    # random seed
    parser.add_argument('--random_seed', type=int, default=2021, help='random seed')

    # basic config
    parser.add_argument('--is_pretraining', type=int, default=0, help='status')
    parser.add_argument('--num_freeze_layers', type=int, default=0,
                        help='num of transformer freeze layer. 0: finetune all layers or do not transfer learning')

    parser.add_argument('--is_inference', type=int, default=0, help='status')

    parser.add_argument('--run_name', type=str, default=None, help='run name, if None: setting is run name')
    parser.add_argument('--model_id', type=str, default='test', help='model id')
    parser.add_argument('--model', type=str, default='PatchTST',
                        help='model name, options: [Autoformer, Informer, Transformer, DLinear, NLinear, Linear, PatchTST, PatchCDTST, Naive_repeat, Arima]')
    # data loader
    parser.add_argument('--data', type=str, default='DKASC', help='dataset type. ex: DKASC, GIST')
    parser.add_argument('--root_path', type=str, default='./data/DKASC_AliceSprings/converted', help='root path of the source domain data file')
    parser.add_argument('--data_path', type=str, default=None, 
                        help='write a PV array name when training a single PV array')
    
    # parser.add_argument('--root_path', type=str, default='./data/GIST_dataset/', help='root path of the source domain data file')
    # parser.add_argument('--data_path', type=str, default='GIST_sisuldong.csv', help='source domain data file')
    parser.add_argument('--scaler', type=bool, default=True, help='StandardScaler')
    parser.add_argument('--freq', type=str, default='h',
                        help='freq for time 2 encoding, options:[s:secondly, t:minutely, h:hourly, d:daily, b:business days, w:weekly, m:monthly], you can also use more detailed freq like 15min or 3h')
    parser.add_argument('--checkpoints', type=str, default='./checkpoints/', help='location of model checkpoints')

    # forecasting task
    parser.add_argument('--seq_len', type=int, default=240, help='input sequence length')
    parser.add_argument('--label_len', type=int, default=0, help='start token length') # decoder 있는 모델에서 사용
    parser.add_argument('--pred_len', type=int, default=16, help='prediction sequence length')

    # DLinear
    # parser.add_argument('--individual', action='store_true', default=False, help='DLinear: a linear layer for each variate(channel) individually')

    # PatchTST
    parser.add_argument('--fc_dropout', type=float, default=0.05, help='fully connected dropout')
    parser.add_argument('--head_dropout', type=float, default=0.0, help='head dropout')
    parser.add_argument('--patch_len', type=int, default=16, help='patch length')
    parser.add_argument('--stride', type=int, default=8, help='stride')
    parser.add_argument('--padding_patch', default='end', help='None: None; end: padding on the end')
    parser.add_argument('--revin', type=int, default=1, help='RevIN; True 1 False 0')
    parser.add_argument('--affine', type=int, default=0, help='RevIN-affine; True 1 False 0')
    parser.add_argument('--subtract_last', type=int, default=0, help='0: subtract mean; 1: subtract last')
    parser.add_argument('--decomposition', type=int, default=0, help='decomposition; True 1 False 0')
    parser.add_argument('--kernel_size', type=int, default=25, help='decomposition-kernel')
    parser.add_argument('--individual', type=int, default=0, help='individual head; True 1 False 0')

    # Formers 
    parser.add_argument('--embed_type', type=int, default=0, help='0: default 1: value embedding + temporal embedding + positional embedding 2: value embedding + temporal embedding 3: value embedding + positional embedding 4: value embedding')
    parser.add_argument('--enc_in', type=int, default=5, help='encoder input size') # DLinear with --individual, use this hyperparameter as the number of channels
    parser.add_argument('--dec_in', type=int, default=5, help='decoder input size')
    parser.add_argument('--c_out', type=int, default=1, help='output size')
    parser.add_argument('--d_model', type=int, default=512, help='dimension of model')
    parser.add_argument('--n_heads', type=int, default=8, help='num of heads')
    parser.add_argument('--e_layers', type=int, default=2, help='num of encoder layers')
    parser.add_argument('--d_layers', type=int, default=1, help='num of decoder layers')
    parser.add_argument('--d_ff', type=int, default=2048, help='dimension of fcn')
    parser.add_argument('--moving_avg', type=int, default=25, help='window size of moving average')
    parser.add_argument('--factor', type=int, default=1, help='attn factor')
    parser.add_argument('--distil', action='store_false',
                        help='whether to use distilling in encoder, using this argument means not using distilling',
                        default=True)
    parser.add_argument('--dropout', type=float, default=0.05, help='dropout')
    parser.add_argument('--embed', type=str, default='timeF',
                        help='time features encoding, options:[timeF, fixed, learned]')
    parser.add_argument('--activation', type=str, default='gelu', help='activation')
    parser.add_argument('--output_attention', action='store_true', help='whether to output attention in ecoder')
    parser.add_argument('--do_predict', action='store_true', help='whether to predict unseen future data')
    
    #LSTM
    parser.add_argument('--input_dim', type=int, default=5, help='input dimension')
    parser.add_argument('--hidden_dim', type=int, default=128, help='hidden dimension')
    parser.add_argument('--num_layers', type=int, default=2, help='number of layers')
    parser.add_argument('--bidirectional', type=bool, default=True, help='bidirectional')
    
    # optimization
    parser.add_argument('--num_workers', type=int, default=10, help='data loader num workers')
    parser.add_argument('--itr', type=int, default=1, help='experiments times')
    parser.add_argument('--train_epochs', type=int, default=200, help='train epochs')
    parser.add_argument('--batch_size', type=int, default=128, help='batch size of train input data')
    parser.add_argument('--patience', type=int, default=10, help='early stopping patience')
    parser.add_argument('--learning_rate', type=float, default=0.0001, help='optimizer learning rate')
    parser.add_argument('--des', type=str, default='test', help='exp description')
    parser.add_argument('--loss', type=str, default='mse', help='loss function')
    parser.add_argument('--lradj', type=str, default='type3', help='adjust learning rate')
    parser.add_argument('--pct_start', type=float, default=0.3, help='pct_start')
    parser.add_argument('--use_amp', action='store_true', help='use automatic mixed precision training', default=False)

    # GPU
    parser.add_argument('--use_gpu', type=bool, default=True, help='use gpu')
    parser.add_argument('--gpu', type=int, default=0, help='gpu')
    parser.add_argument('--use_multi_gpu', action='store_true', help='use multiple gpus', default=False)
    parser.add_argument('--devices', type=str, default='0', help='device ids of multile gpus')
    parser.add_argument('--test_flop', action='store_true', default=False, help='See utils/tools for usage')

    parser.add_argument('--resume', action='store_true', default=False, help='resume')

    parser.add_argument('--world_size', default=1, type=int, help='number of distributed processes')
    parser.add_argument('--local_rank', default=-1, type=int)
    parser.add_argument('--dist_url', default='env://', help='url used to set up distributed training')
    parser.add_argument('--dist_on_itp', action='store_true', help='Use distributed training on internal cluster')
    parser.add_argument('--distributed', action='store_true', help='Use distributed training', default=False)
    parser.add_argument('--wandb', action='store_true', help='Use wandb')
    # parser.add_argument('--wandb', type=bool, default=True, help='Use wandb')
    
    args = parser.parse_args()

    # random seed
    fix_seed = args.random_seed
    random.seed(fix_seed)
    torch.manual_seed(fix_seed)
    np.random.seed(fix_seed)

    args.use_gpu = True if torch.cuda.is_available() and args.use_gpu else False

    if args.use_gpu and args.use_multi_gpu:
        args.dvices = args.devices.replace(' ', '')
        device_ids = args.devices.split(',')
        args.device_ids = [int(id_) for id_ in device_ids]
        args.gpu = args.device_ids[0]

    if args.local_rank == -1:
        print('Args in experiment:')
        print(args)
    
    Exp = Exp_Main
    
    if (args.is_pretraining) and (not args.is_inference):
        for ii in range(args.itr):
            # setting record of experiments
            setting = '{}_{}_{}_sl{}_ll{}_pl{}_dm{}_nh{}_el{}_dl{}_df{}_fc{}_eb{}_dt{}_{}_wb{}_{}'.format(
                args.model_id,
                args.model,
                args.data,
                args.seq_len,
                args.label_len,
                args.pred_len,
                args.d_model,
                args.n_heads,
                args.e_layers,
                args.d_layers,
                args.d_ff,
                args.factor,
                args.embed,
                args.distil,
                args.des,
                args.num_freeze_layers,
                args.wandb,
                ii)

            exp = Exp(args)  # set experiments
            if args.local_rank == -1:
                print('>>>>>>>start pretraining : {}>>>>>>>>>>>>>>>>>>>>>>>>>>'.format(setting))
            exp.train(args.checkpoints)

            # TODO: metric 계산하는거 개선해야 함.
            # if args.local_rank == 0:
            #     print('>>>>>>>testing : {}<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<'.format(setting))
            # exp.test(setting)
            print('Training Done')

            if args.do_predict:
                if args.local_rank == 0:
                    print('>>>>>>>predicting : {}<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<'.format(setting))
                exp.predict(setting, True)

            torch.cuda.empty_cache()

    elif args.is_inference:
        ii = 0
        setting = '{}_{}_{}_sl{}_ll{}_pl{}_dm{}_nh{}_el{}_dl{}_df{}_fc{}_eb{}_dt{}_{}_wb{}_{}'.format(
            args.model_id,
            args.model,
            args.data,
            args.seq_len,
            args.label_len,
            args.pred_len,
            args.d_model,
            args.n_heads,
            args.e_layers,
            args.d_layers,
            args.d_ff,
            args.factor,
            args.embed,
            args.distil,
            args.des,
            args.wandb,
            ii)    

        exp = Exp(args)  # set experiments
        if args.local_rank == 0:
            print('>>>>>>>testing : {}<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<'.format(setting))
        exp.test(args.checkpoints, test=1)
        torch.cuda.empty_cache()
    
    elif args.num_freeze_layers > 0:    # freeze block 개수 조절을 통해 finetuning 및 linear probing 수행
        for ii in range(args.itr):
            # setting record of experiments
            setting = '{}_{}_{}_{}_sl{}_ll{}_pl{}_dm{}_nh{}_el{}_dl{}_df{}_fc{}_eb{}_dt{}_{}_wb{}_{}'.format(
                args.num_freeze_layers,
                args.model_id,
                args.model,
                args.data,
                args.seq_len,
                args.label_len,
                args.pred_len,
                args.d_model,
                args.n_heads,
                args.e_layers,
                args.d_layers,
                args.d_ff,
                args.factor,
                args.embed,
                args.distil,
                args.des,
                args.wandb,
                ii)

            exp = Exp_Finetune(args)
            
            if args.is_fully_finetune:
                if args.local_rank == 0:
                    print('>>>>>>>start fully finetuning : {}>>>>>>>>>>>>>>>>>>>>>>>>>>'.format(setting))
                exp.fully_finetune(args.checkpoints, args.resume)

            elif args.is_linear_probe:
                if args.local_rank == 0:
                    print('>>>>>>>start linear probing : {}>>>>>>>>>>>>>>>>>>>>>>>>>>'.format(setting))
                exp.linear_probe(args.checkpoints, args.resume)       

            torch.cuda.empty_cache()
