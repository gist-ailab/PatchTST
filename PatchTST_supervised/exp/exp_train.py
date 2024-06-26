from data_provider.data_factory import data_provider
from exp.exp_basic import Exp_Basic
from exp.exp_main import Exp_Main
from models import Informer, Autoformer, Transformer, DLinear, Linear, NLinear, PatchTST, PatchCDTST, LSTM
from models.Stat_models import Naive_repeat, Arima
from utils.tools import EarlyStopping, adjust_learning_rate, visual, test_params_flop, visual_out, visual_original
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

class Exp_Train(Exp_Main):
    def __init__(self, args):
        super(Exp_Train, self).__init__(args)
        self.args = args
        self.data_provider = data_provider

    def _build_model(self):
        model_dict = {
            'Autoformer': Autoformer,
            'Transformer': Transformer,
            'Informer': Informer,
            'DLinear': DLinear,
            'NLinear': NLinear,
            'Linear': Linear,
            'PatchTST': PatchTST,
            'Naive_repeat': Naive_repeat,
            'Arima': Arima,
            'LSTM': LSTM
        }
        if self.args.model == 'LSTM':
            model = model_dict[self.args.model].Model(self.args, self.device).float()
        else: model = model_dict[self.args.model].Model(self.args).float()

        return model

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
            train_loss = []

            self.model.train()
            epoch_time = time.time()

            for i, data in enumerate(train_loader):
                iter_count += 1
                model_optim.zero_grad()

                batch_x, batch_y, batch_x_mark, batch_y_mark = data
                batch_x = batch_x.to(self.device).float()
                batch_y = batch_y.to(self.device).float()
                batch_x_mark = batch_x_mark.to(self.device).float()
                batch_y_mark = batch_y_mark.to(self.device).float()

                # decoder input
                dec_inp = torch.zeros_like(batch_y[:, -self.args.pred_len:, :]).float()
                dec_inp = torch.cat([batch_y[:, :self.args.label_len, :], dec_inp], dim=1).float().to(self.device)

               
                if self.args.use_amp:
                    with torch.cuda.amp.autocast():
                        if 'Linear' in self.args.model or 'TST' in self.args.model or 'LSTM' in self.args.model:
                            outputs = self.model(batch_x)
                        elif 'LSTM' in self.args.model:
                                outputs = self.model(batch_x, dec_inp)
                        else:
                            if self.args.output_attention:
                                outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)[0]
                            else:
                                outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)
                                
                else:
                    if 'Linear' in self.args.model or 'TST' in self.args.model:
                        outputs = self.model(batch_x)
                    elif 'LSTM' in self.args.model:
                        outputs = self.model(batch_x, dec_inp)
                    else:
                        if self.args.output_attention:
                            outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)[0]
                        else:
                            outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)
                
                f_dim = -1 if self.args.features == 'MS' else 0

                outputs = outputs[:, -self.args.pred_len:, f_dim:].to(self.device)
                batch_y = batch_y[:, -self.args.pred_len:, f_dim:].to(self.device)
                loss = criterion(outputs, batch_y)
                train_loss.append(loss.item())

                if (i + 1) % 100 == 0:
                    print(f"\titers: {i+1}, epoch: {epoch+1} | loss: {loss.item():.7f}, ")
                    
                    speed = (time.time() - time_now) / iter_count
                    left_time = speed * ((self.args.train_epochs - epoch) * train_steps - i)
                    print('\tspeed: {:.4f}s/iter; left time: {:.4f}s'.format(speed, left_time))
                    iter_count = 0
                    time_now = time.time()

                if self.args.use_amp:
                    scaler.scale(loss).backward()
                    scaler.step(model_optim)
                    scaler.update()
                else:
                    loss.backward()
                    model_optim.step()  

                if self.args.lradj == 'TST':
                    adjust_learning_rate(model_optim, scheduler, epoch + 1, self.args, printout=False)
                    scheduler.step()      

            print("Epoch: {} cost time: {}".format(epoch + 1, time.time() - epoch_time))
            train_loss = np.average(train_loss)
            vali_loss = self.vali(vali_data, vali_loader, criterion)
            test_loss = self.vali(test_data, test_loader, criterion)                
            
            print("Epoch: {0}, Steps: {1} | Train Loss: {2:.7f} Vali Loss: {3:.7f} Test Loss: {4:.7f}".format(
                epoch + 1, train_steps, train_loss, vali_loss, test_loss))
            
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
                batch_y = batch_y.float().to(self.device)

                batch_x_mark = batch_x_mark.float().to(self.device)
                batch_y_mark = batch_y_mark.float().to(self.device)

                # decoder input
                dec_inp = torch.zeros_like(batch_y[:, -self.args.pred_len:, :]).float()
                dec_inp = torch.cat([batch_y[:, :self.args.label_len, :], dec_inp], dim=1).float().to(self.device)                
                
                if self.args.use_amp:
                    with torch.cuda.amp.autocast():
                        if 'Linear' in self.args.model or 'TST' in self.args.model:
                            outputs = self.model(batch_x)
                        elif 'LSTM' in self.args.model:
                            outputs = self.model(batch_x, dec_inp)
                        else:
                            if self.args.output_attention:
                                outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)[0]
                            else:
                                outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)
                else:
                    if 'Linear' in self.args.model or 'TST' in self.args.model:
                        outputs = self.model(batch_x)
                    elif 'LSTM' in self.args.model:
                            outputs = self.model(batch_x, dec_inp)
                    else:
                        if self.args.output_attention:
                            outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)[0]
                        else:
                            outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)

                f_dim = -1 if self.args.features == 'MS' else 0
                outputs = outputs[:, -self.args.pred_len:, f_dim:]
                batch_y = batch_y[:, -self.args.pred_len:, f_dim:].to(self.device)                
                pred = outputs.detach().cpu()
                true = batch_y.detach().cpu()

                loss = criterion(pred, true)

                total_loss.append(loss)
            total_loss = np.average(total_loss)
            self.model.train()
            return total_loss  
    
    def test(self, setting, test=0):
        test_data, test_loader = self._get_data(flag='test')
        
        if test:
            print('loading model')
            self.model.load_state_dict(torch.load(os.path.join('./checkpoints/' + setting, 'checkpoint.pth')))

        preds = []
        trues = []
        inputx = []
        preds_inverse = []
        trues_inverse = []
        folder_path = './test_results/' + setting + '/'
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

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
                        elif 'LSTM' in self.args.model:
                            outputs = self.model(batch_x, dec_inp)
                        else:
                            if self.args.output_attention:
                                outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)[0]
                            else:
                                outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)
                else:
                    if 'Linear' in self.args.model or 'TST' in self.args.model:
                        outputs = self.model(batch_x)
                    elif 'LSTM' in self.args.model:
                        outputs = self.model(batch_x, dec_inp)
                    else:
                        if self.args.output_attention:
                            outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)[0]

                        else:
                            outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)

                f_dim = -1 if self.args.features == 'MS' else 0
                # print(outputs.shape,batch_y.shape)
                outputs = outputs[:, -self.args.pred_len:, f_dim:]
                batch_y = batch_y[:, -self.args.pred_len:, f_dim:].to(self.device)
                outputs = outputs.detach().cpu().numpy()
                batch_y = batch_y.detach().cpu().numpy()

                pred = outputs  # outputs.detach().cpu().numpy()  # .squeeze()
                true = batch_y  # batch_y.detach().cpu().numpy()  # .squeeze()

                pred_inverse = test_data.inverse_transform(outputs.detach().cpu().numpy())
                true_inverse = test_data.inverse_transform(batch_y.detach().cpu().numpy())
                preds.append(pred)
                trues.append(true)

                preds_inverse.append(pred_inverse)
                trues_inverse.append(true_inverse)
                
                inputx.append(batch_x.detach().cpu().numpy())
                
                if i % 20 == 0:
                    input = batch_x.detach().cpu().numpy()
                    gt = np.concatenate((input[0, :, -1], true[0, :, -1]), axis=0)
                    pd = np.concatenate((input[0, :, -1], pred[0, :, -1]), axis=0)
                    visual_original(gt, pd, os.path.join(folder_path, str(i) + '.png'))

        if self.args.test_flop:
            test_params_flop((batch_x.shape[1],batch_x.shape[2]))
            exit()

        preds = np.array(preds)
        trues = np.array(trues)
        preds_inverse = np.array(preds_inverse)
        trues_inverse = np.array(trues_inverse)

        inputx = np.array(inputx)



        preds = preds.reshape(-1, preds.shape[-2], preds.shape[-1])
        trues = trues.reshape(-1, trues.shape[-2], trues.shape[-1])
        preds_inverse = preds_inverse.reshape(-1, preds_inverse.shape[-2], preds_inverse.shape[-1])
        trues_inverse = trues_inverse.reshape(-1, trues_inverse.shape[-2], trues_inverse.shape[-1])
        inputx = inputx.reshape(-1, inputx.shape[-2], inputx.shape[-1])



        # result save
        folder_path = './results/' + setting + '/'
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        mae, mse, rmse, mape, mspe, rse, corr = metric(preds, trues)
        mae_i, mse_i, rmse_i, mape_i, mspe_i, rse_i, corr_i = metric(preds_inverse, trues_inverse)
        print('mse:{}, mae:{}, rmse:{}, map:{}, rse:{}, corr:{}'.format(mae, mse, rmse, mape, mspe, rse, corr))
        print('mse_inverse:{}, mae_inverse:{}, rmse_inverse:{}, map_inverse:{}, rse_inverse:{}, corr_inverse:{}'.format(mae_i, mse_i, rmse_i, mape_i, mspe_i, rse_i, corr_i))
        f = open("result.txt", 'a')
        f.write(setting + "  \n")
        f.write('mse:{}, mae:{}, rmse:{}, map:{}, rse:{}, corr:{}'.format(mae, mse, rmse, mape, mspe, rse, corr))
        f.write('mse_inverse:{}, mae_inverse:{}, rmse_inverse:{}, map_inverse:{}, rse_inverse:{}, corr_inverse:{}'.format(mae_i, mse_i, rmse_i, mape_i, mspe_i, rse_i, corr_i))

        f.write('\n')
        f.write('\n')
        f.close()

        # np.save(folder_path + 'metrics.npy', np.array([mae, mse, rmse, mape, mspe,rse, corr]))
        np.save(folder_path + 'pred.npy', preds)
        np.save(folder_path + 'pred_inverse.npy', preds_inverse)
        # np.save(folder_path + 'true.npy', trues)
        # np.save(folder_path + 'x.npy', inputx)
        return
    
    def predict(self, setting, load=False):
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
                    batch_y = batch_y.float().to(self.device)
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
                            elif 'LSTM' in self.args.model:
                                outputs = self.model(batch_x, dec_inp)
                            else:
                                if self.args.output_attention:
                                    outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)[0]
                                else:
                                    outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)
                    else:
                        if 'Linear' in self.args.model or 'TST' in self.args.model:
                            outputs = self.model(batch_x)
                        elif 'LSTM' in self.args.model:
                            outputs = self.model(batch_x, dec_inp)
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
            folder_path = './results/' + setting + '/'
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)

            np.save(folder_path + 'real_prediction.npy', preds)

            return
                # if self.args.model != 'LSTM':
                #     active_power = outputs[:, :, -1].detach().cpu()
                #     active_power_gt = batch_y[:, :, -1].detach().cpu()
                #     active_power_np = vali_data.inverse_transform(active_power)
                #     active_power_gt_np = vali_data.inverse_transform(active_power_gt)

                #     pred = torch.from_numpy(active_power_np)
                #     gt = torch.from_numpy(active_power_gt_np)
                
                # else:
                #     pred_np = vali_data.inverse_transform(outputs.detach().cpu().numpy())
                #     gt_np = vali_data.inverse_transform(batch_y.detach().cpu().numpy())

                #     pred = torch.from_numpy(pred_np)
                #     gt = torch.from_numpy(gt_np)

                # loss = criterion(pred, gt)

                # total_loss.append(loss)