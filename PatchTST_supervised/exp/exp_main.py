from data_provider.data_factory import data_provider
from exp.exp_basic import Exp_Basic
from models import Informer, Autoformer, Transformer, DLinear, Linear, NLinear, PatchTST, PatchCDTST, LSTM
from models.Stat_models import Naive_repeat, Arima
from utils.tools import EarlyStopping, adjust_learning_rate, visual, test_params_flop, visual_out
from utils.metrics import metric
from utils.mmd_loss import MMDLoss

import numpy as np
import torch
import torch.nn as nn
from torch import optim
from torch.optim import lr_scheduler 

import os
import time

import warnings
import matplotlib.pyplot as plt
import numpy as np

warnings.filterwarnings('ignore')

class Exp_Main(Exp_Basic):
    def __init__(self, args):
        super(Exp_Main, self).__init__(args)

    def _build_model(self):
        model_dict = {
            'Autoformer': Autoformer,
            'Transformer': Transformer,
            'Informer': Informer,
            'DLinear': DLinear,
            'NLinear': NLinear,
            'Linear': Linear,
            'PatchTST': PatchTST,
            'PatchCDTST': PatchCDTST,
            'Naive_repeat': Naive_repeat,
            'Arima': Arima,
            'LSTM': LSTM
        }
        model = model_dict[self.args.model].Model(self.args).float()

        if self.args.use_multi_gpu and self.args.use_gpu:
            model = nn.DataParallel(model, device_ids=self.args.device_ids)
        return model

    def _get_data(self, flag):
        data_set, data_loader = data_provider(self.args, flag)
        return data_set, data_loader

    def _select_optimizer(self):
        model_optim = optim.Adam(self.model.parameters(), lr=self.args.learning_rate)
        return model_optim

    def _select_criterion(self):
        criterion = nn.MSELoss()
        cross_criterion = MMDLoss()
        if self.args.model == 'PatchCDTST' and self.args.is_training:
            return criterion, cross_criterion
        return criterion

    def train(self, setting, exp_id, resume):
        train_data, train_loader = self._get_data(flag='train')
        vali_data, vali_loader = self._get_data(flag='val')
        test_data, test_loader = self._get_data(flag='test')

        if 'checkpoint.pth' in self.args.checkpoints.split('/'):
            path = self.args.checkpoints
        else:
            path = os.path.join(self.args.checkpoints, exp_id, setting)

        if not os.path.exists(path):
            os.makedirs(path)

        time_now = time.time()

        train_steps = len(train_loader)
        early_stopping = EarlyStopping(patience=self.args.patience, verbose=True)

        model_optim = self._select_optimizer()
        
        if self.args.model == 'PatchCDTST':
            criterion, cross_criterion = self._select_criterion()
        else:
            criterion = self._select_criterion()
            
        if self.args.use_amp:
            scaler = torch.cuda.amp.GradScaler()
            
        scheduler = lr_scheduler.OneCycleLR(optimizer = model_optim,
                                            steps_per_epoch = train_steps,
                                            pct_start = self.args.pct_start,
                                            epochs = self.args.train_epochs,
                                            max_lr = self.args.learning_rate)

        if resume:
            latest_model_path = path + '/' + 'model_latest.pth'
            self.model.load_state_dict(torch.load(latest_model_path))
            print('model loaded from {}'.format(latest_model_path))


        for epoch in range(self.args.train_epochs):
            iter_count = 0
            train_loss_s = []
            train_loss_t = []            
            train_mmd_loss = []
            train_loss = []

            self.model.train()
            epoch_time = time.time()
            # for i, (batch_x, batch_y, batch_x_mark, batch_y_mark) in enumerate(train_loader):
            for i, data in enumerate(train_loader):
                iter_count += 1
                model_optim.zero_grad()
                
                if len(data) == 4: # Original data loader
                    batch_x_s, batch_y_s, batch_x_mark_s, batch_y_mark_s = data
                    batch_x_s = batch_x_s.float().to(self.device)
                    batch_y_s = batch_y_s.float().to(self.device)
                    batch_x_mark_s = batch_x_mark_s.float().to(self.device)
                    batch_y_mark_s = batch_y_mark_s.float().to(self.device)
                
                elif len(data) == 8: # Data loader for PatchCDTST
                    batch_x_s, batch_y_s, batch_x_mark_s, batch_y_mark_s, batch_x_t, batch_y_t, batch_x_mark_t, batch_y_mark_t = data   # s for source, t for target
                    batch_x_s = batch_x_s.float().to(self.device)
                    batch_y_s = batch_y_s.float().to(self.device)
                    batch_x_mark_s = batch_x_mark_s.float().to(self.device)
                    batch_y_mark_s = batch_y_mark_s.float().to(self.device)
                    batch_x_t = batch_x_t.float().to(self.device)
                    batch_y_t = batch_y_t.float().to(self.device)
                    batch_x_mark_t = batch_x_mark_t.float().to(self.device)
                    batch_y_mark_t = batch_y_mark_t.float().to(self.device)
                    
                # 원래 있던 것.
                # batch_x = batch_x.float().to(self.device)
                # batch_y = batch_y.float().to(self.device)
                # batch_x_mark = batch_x_mark.float().to(self.device)
                # batch_y_mark = batch_y_mark.float().to(self.device)

                # decoder input
                dec_inp = torch.zeros_like(batch_y_s[:, -self.args.pred_len:, :]).float()
                dec_inp = torch.cat([batch_y_s[:, :self.args.label_len, :], dec_inp], dim=1).float().to(self.device)

                # encoder - decoder
                if self.args.use_amp:
                    with torch.cuda.amp.autocast():
                        if 'Linear' in self.args.model or 'TST' in self.args.model or 'LSTM' in self.args.model:
                            if 'CD' in self.args.model:
                                source_outputs, target_outputs, target_feat, cross_feat = self.model(batch_x_s, batch_x_t)
                            else:
                                source_outputs = self.model(batch_x_s)
                        else:
                            if self.args.output_attention:
                                source_outputs = self.model(batch_x_s, batch_x_mark_s, dec_inp, batch_y_mark_s)[0]
                            else:
                                source_outputs = self.model(batch_x_s, batch_x_mark_s, dec_inp, batch_y_mark_s)

                else:
                    if 'Linear' in self.args.model or 'TST' in self.args.model or 'LSTM' in self.args.model:
                        if 'CD' in self.args.model:
                            source_outputs, target_outputs, target_feat, cross_feat = self.model(batch_x_s, batch_x_t)
                        else:
                            source_outputs = self.model(batch_x_s)
                    else:
                        if self.args.output_attention:
                            source_outputs = self.model(batch_x_s, batch_x_mark_s, dec_inp, batch_y_mark_s)[0]
                            
                        else:
                            source_outputs = self.model(batch_x_s, batch_x_mark_s, dec_inp, batch_y_mark_s, batch_y_s)
                            # TODO: batch_y_s 의 역할이 뭐지??? TST 계열에선 안 쓰긴 한다.
                            # print(outputs.shape,batch_y.shape)
                            
                f_dim = -1 if self.args.features == 'MS' else 0
                
                # loss for source domain
                source_outputs = source_outputs[:, -self.args.pred_len:, f_dim:]
                batch_y_s = batch_y_s[:, -self.args.pred_len:, f_dim:].to(self.device)
                loss_s = criterion(source_outputs, batch_y_s)
                # train_loss_s.append(loss_s.item())
                
             
                
                if 'CDTST' in self.args.model:
                    # loss for target domain
                    target_outputs = target_outputs[:, -self.args.pred_len:, f_dim:]
                    batch_y_t = batch_y_t[:, -self.args.pred_len:, f_dim:].to(self.device)
                    loss_t = criterion(target_outputs, batch_y_t)
                    # train_loss_t.append(loss_t.item())
                    
                    # loss for cross-domain
                    target_feat = target_feat[:, -self.args.pred_len:, f_dim:]
                    cross_feat = cross_feat[:, -self.args.pred_len:, f_dim:]
                    mmd_loss = cross_criterion(target_feat, cross_feat)
                    # train_mmd_loss.append(mmd_loss.item())
                    total_loss = loss_s + loss_t + mmd_loss
                else:
                    total_loss = loss_s
                    
                train_loss.append(total_loss.item())
                    
                                    
                
                if (i + 1) % 100 == 0:
                    print(f"\titers: {i+1}, epoch: {epoch+1} | loss: {total_loss.item():.7f}, ")
                    if 'CDTST' in self.args.model:
                        print(f"loss_source: {loss_s.item():.7f}, loss_target: {loss_t.item():.7f}, mmd_loss: {mmd_loss.item():.7f} \n")
                    
                    speed = (time.time() - time_now) / iter_count
                    left_time = speed * ((self.args.train_epochs - epoch) * train_steps - i)
                    print('\tspeed: {:.4f}s/iter; left time: {:.4f}s'.format(speed, left_time))
                    iter_count = 0
                    time_now = time.time()

                if self.args.use_amp:
                    scaler.scale(total_loss).backward()
                    scaler.step(model_optim)
                    scaler.update()
                    
                else:
                    total_loss.backward()
                    model_optim.step()
                    
                if self.args.lradj == 'TST':
                    adjust_learning_rate(model_optim, scheduler, epoch + 1, self.args, printout=False)
                    scheduler.step()

            print(f"Epoch: {epoch + 1} | cost time: {time.time() - epoch_time}")
            
            train_loss = np.average(train_loss)
            vali_loss = self.vali(vali_data, vali_loader, criterion)
            test_loss = self.vali(test_data, test_loader, criterion)
            
            print(f"Epoch: {epoch + 1} | Train Loss: {train_loss:.7f}, Vali Loss: {vali_loss:.7f}, Test Loss: {test_loss:.7f}")
            early_stopping(vali_loss, self.model, path)
            if early_stopping.early_stop:
                print("Early stopping")
                break

            if self.args.lradj != 'TST':
                adjust_learning_rate(model_optim, scheduler, epoch + 1, self.args)
            else:
                print('Updating learning rate to {}'.format(scheduler.get_last_lr()[0]))
            

        best_model_path = path + '/' + 'checkpoint.pth'
        self.model.load_state_dict(torch.load(best_model_path))

        return self.model

    def vali(self, vali_data, vali_loader, criterion):
        total_loss = []
        self.model.eval()
        with torch.no_grad():
            for i, (batch_x, batch_y, batch_x_mark, batch_y_mark) in enumerate(vali_loader):
                batch_x = batch_x.float().to(self.device)
                batch_y = batch_y.float()

                batch_x_mark = batch_x_mark.float().to(self.device)
                batch_y_mark = batch_y_mark.float().to(self.device)

                # decoder input
                dec_inp = torch.zeros_like(batch_y[:, -self.args.pred_len:, :]).float()
                dec_inp = torch.cat([batch_y[:, :self.args.label_len, :], dec_inp], dim=1).float().to(self.device)
                # encoder - decoder
                if self.args.use_amp:
                    with torch.cuda.amp.autocast():
                        if 'Linear' in self.args.model or 'TST' in self.args.model:
                            outputs = self.model(batch_x)
                        else:
                            if self.args.output_attention:
                                outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)[0]
                            else:
                                outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)
                else:
                    if 'Linear' in self.args.model or 'TST' in self.args.model:
                        outputs = self.model(batch_x)
                    else:
                        if self.args.output_attention:
                            outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)[0]
                        else:
                            outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)
                f_dim = -1 if self.args.features == 'MS' else 0
                
                # ### calculate metrics with only active power
                outputs = outputs[:, -self.args.pred_len:, f_dim:]
                batch_y = batch_y[:, -self.args.pred_len:, f_dim:].to(self.device)
                active_power = outputs[:, :, -1].detach().cpu()
                active_power_gt = batch_y[:, :, -1].detach().cpu()

                # de-normalize the data and prediction values
                active_power_np = vali_data.inverse_transform(active_power)
                active_power_gt_np = vali_data.inverse_transform(active_power_gt)
                
                pred = torch.from_numpy(active_power_np)
                gt = torch.from_numpy(active_power_gt_np)
                
                loss = criterion(pred, gt)

                total_loss.append(loss)
        total_loss = np.average(total_loss)
        self.model.train()
        return total_loss



    def test(self, setting, exp_id, model_path=None, test=0):
        test_data, test_loader = self._get_data(flag='test')
        
        # pv_max = test_loader.sampler.data_source.pv_max
        # pv_min = test_loader.sampler.data_source.pv_min
        
        if test:
            print('loading model')
            if model_path != None:
                self.model.load_state_dict(torch.load(model_path))
            else:
                self.model.load_state_dict(torch.load(os.path.join('./checkpoints/', f'exp{exp_id}', setting, 'checkpoint.pth')))
            
        preds = []
        trues = []
        inputx = []
        folder_path_inout = './test_results/' + exp_id + '/in+out/' + setting + '/'
        folder_path_out = './test_results/' + exp_id + '/out/' + setting + '/'
        if not os.path.exists(folder_path_inout):
            os.makedirs(folder_path_inout)
        if not os.path.exists(folder_path_out):
            os.makedirs(folder_path_out)

        self.model.eval()
        with torch.no_grad():
            for i, (batch_x, batch_y, batch_x_mark, batch_y_mark) in enumerate(test_loader):
                batch_x = batch_x.float().to(self.device)
                batch_y = batch_y.float().to(self.device)

                batch_x_mark = batch_x_mark.float().to(self.device)
                batch_y_mark = batch_y_mark.float().to(self.device)

                # decoder input
                dec_inp = torch.zeros_like(batch_y[:, -self.args.pred_len:, :]).float()
                dec_inp = torch.cat([batch_y[:, :self.args.label_len, :], dec_inp], dim=1).float().to(self.device)
                # encoder - decoder
                if self.args.use_amp:
                    with torch.cuda.amp.autocast():
                        if 'Linear' in self.args.model or 'TST' in self.args.model:
                            outputs = self.model(batch_x)
                        else:
                            if self.args.output_attention:
                                outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)[0]
                            else:
                                outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)
                else:
                    if 'Linear' in self.args.model or 'TST' in self.args.model:
                            outputs = self.model(batch_x)
                    else:
                        if self.args.output_attention:
                            outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)[0]

                        else:
                            outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)

                f_dim = -1 if self.args.features == 'MS' else 0
                # print(outputs.shape,batch_y.shape)
                
                # ### calculate metrics with only active power, BSH
                ### Last column is active power
                active_power = outputs[:, :, -1]
                active_power_gt = batch_y[:, :, -1]
                
                active_power_np = active_power.detach().cpu().numpy()
                active_power_gt_np = active_power_gt.detach().cpu().numpy()
                
                # de-normalize the data and prediction values
                pred = test_data.inverse_transform(active_power_np)
                true = test_data.inverse_transform(active_power_gt_np)
                # ### calculate metrics with only active power, BSH  

                preds.append(pred)
                trues.append(true[:,-self.args.pred_len:])
                inputx.append(batch_x.detach().cpu().numpy())
                if i % 10 == 0:
                    # visualize_input_length = outputs.shape[1]*3 # visualize three times of the prediction length
                    input_np = batch_x[:, :, -1].detach().cpu().numpy()
                    
                    input_inverse_transform = test_data.inverse_transform(input_np)
                    input_seq = input_inverse_transform[0,:]
                    gt = true[0, -self.args.pred_len:]
                    pd = pred[0, :]
                    visual(input_seq, gt, pd, os.path.join(folder_path_inout, str(i) + '.png'))
                    visual_out(input_seq, gt, pd, os.path.join(folder_path_out, str(i) + '.png'))

        if self.args.test_flop:
            test_params_flop((batch_x.shape[1],batch_x.shape[2]))
            exit()
        preds = np.array(preds)
        trues = np.array(trues)
        inputx = np.array(inputx)

        preds = preds.reshape(-1, preds.shape[-2], preds.shape[-1])
        trues = trues.reshape(-1, trues.shape[-2], trues.shape[-1])
        inputx = inputx.reshape(-1, inputx.shape[-2], inputx.shape[-1])

        # result save
        folder_path = './results/' + exp_id+ '/' + setting + '/'
        os.makedirs(folder_path, exist_ok=True)

        # mae, mse, rmse, mape, mspe, rse, corr = metric(preds, trues)
        # print('mse:{}, mae:{}, rse:{}'.format(mse, mae, rse))
        # f = open("result.txt", 'a')
        # f.write(setting + "  \n")
        # f.write('mse:{}, mae:{}, rse:{}'.format(mse, mae, rse))
        # f.write('\n')
        # f.write('\n')
        # f.close()
        
        # calculate metrics with only generated power
        
        mae, mse, rmse = metric(preds, trues)
        print('mse:{}, mae:{}, rmse:{}'.format(mse, mae, rmse))
        txt_save_path = os.path.join(folder_path,
                                     f"{self.args.seq_len}_{self.args.pred_len}_result.txt")
        f = open(txt_save_path, 'a')
        f.write(exp_id + "  \n")
        f.write(setting + "  \n")
        f.write('mse:{}, mae:{}, rmse:{}'.format(mse, mae, rmse))
        f.write('\n')
        f.write('\n')
        f.close()
        
        # np.save(folder_path + 'metrics.npy', np.array([mae, mse, rmse, mape, mspe,rse, corr]))
        np.save(folder_path + 'pred.npy', preds)
        # np.save(folder_path + 'true.npy', trues)
        # np.save(folder_path + 'x.npy', inputx)
        return

    def predict(self, setting, exp_id, load=False):
        pred_data, pred_loader = self._get_data(flag='pred')

        if load:
            path = os.path.join(self.args.checkpoints, setting)
            best_model_path = path + '/' + 'checkpoint.pth'
            self.model.load_state_dict(torch.load(best_model_path))

        preds = []

        self.model.eval()
        with torch.no_grad():
            for i, (batch_x, batch_y, batch_x_mark, batch_y_mark) in enumerate(pred_loader):
                batch_x = batch_x.float().to(self.device)
                batch_y = batch_y.float()
                batch_x_mark = batch_x_mark.float().to(self.device)
                batch_y_mark = batch_y_mark.float().to(self.device)

                # decoder input
                dec_inp = torch.zeros([batch_y.shape[0], self.args.pred_len, batch_y.shape[2]]).float().to(batch_y.device)
                dec_inp = torch.cat([batch_y[:, :self.args.label_len, :], dec_inp], dim=1).float().to(self.device)
                # encoder - decoder
                if self.args.use_amp:
                    with torch.cuda.amp.autocast():
                        if 'Linear' in self.args.model or 'TST' in self.args.model:
                            outputs = self.model(batch_x)
                        else:
                            if self.args.output_attention:
                                outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)[0]
                            else:
                                outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)
                else:
                    if 'Linear' in self.args.model or 'TST' in self.args.model:
                        outputs = self.model(batch_x)
                    else:
                        if self.args.output_attention:
                            outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)[0]
                        else:
                            outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)
                pred = outputs.detach().cpu().numpy()  # .squeeze()
                preds.append(pred)

        preds = np.array(preds)
        preds = preds.reshape(-1, preds.shape[-2], preds.shape[-1])

        # result save
        folder_path = './results/' + exp_id + '/' + setting + '/'
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        np.save(folder_path + 'real_prediction.npy', preds)

        return
