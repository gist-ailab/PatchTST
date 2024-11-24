from data_provider.data_factory import data_provider
from exp.exp_basic import Exp_Basic
from models import Informer, Autoformer, Transformer, DLinear, Linear, NLinear, PatchTST, LSTM
from models.Stat_models import Naive_repeat, Arima
from utils.tools import EarlyStopping, adjust_learning_rate, visual, test_params_flop, visual_out, visual_original
from utils.metrics import MetricEvaluator

import numpy as np
import torch
import torch.nn as nn
from torch import optim
from torch.optim import lr_scheduler
import matplotlib.pyplot as plt
import os

import os
import matplotlib.pyplot as plt
import pandas as pd

import os
import time
import datetime

import warnings
import matplotlib.pyplot as plt
import numpy as np
import wandb
from utils.wandb_uploader import upload_files_to_wandb
from collections import defaultdict

warnings.filterwarnings('ignore')

class Exp_Main(Exp_Basic):
    def __init__(self, args):
        super(Exp_Main, self).__init__(args)
        self.project_name = "pv-forecasting"
        current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_name = f"{self.args.model}_run_{current_time}"

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
        
        model = model_dict[self.args.model].Model(self.args).float()
        
        if self.args.distributed:
            model = nn.parallel.DistributedDataParallel(
                model, device_ids=[self.args.local_rank],
                output_device=self.args.local_rank
            )
        elif self.args.use_multi_gpu and self.args.use_gpu:
            model = nn.DataParallel(model, device_ids=self.args.device_ids)
            
        return model

    def _get_data(self, flag):
        data_set, data_loader = data_provider(self.args, flag, self.args.distributed)
        return data_set, data_loader

    def _select_optimizer(self, part=None):
        if part is None:
            model_optim = optim.Adam(self.model.parameters(), lr=self.args.learning_rate)
        else:
            model_optim = optim.Adam(filter(lambda p: p.requires_grad, self.model.parameters()), lr=self.args.learning_rate)
        return model_optim

    def _select_criterion(self):
        return nn.MSELoss()

    def train(self, setting, resume):
        self._set_wandb(setting)
        
        config = {
            "model": self.args.model,
            "num_parameters": sum(p.numel() for p in self.model.parameters()),
            "batch_size": self.args.batch_size,
            "num_workers": self.args.num_workers,
            "learning_rate": self.args.learning_rate,
            "loss_function": self.args.loss,
            "dataset": self.args.data,
            "epochs": self.args.train_epochs,
            "input_seqeunce_length": self.args.seq_len,
            "prediction_sequence_length": self.args.pred_len,
            "patch_length": self.args.patch_len,
            "stride": self.args.stride,
        }
        upload_files_to_wandb(
            project_name=self.project_name,
            run_name=self.run_name,
            config=config
        )     
        
        train_data, train_loader = self._get_data(flag='train')
        vali_data, vali_loader = self._get_data(flag='val')
        test_data, test_loader = self._get_data(flag='test')

        path = os.path.join(self.args.checkpoints, setting) if 'checkpoint.pth' not in self.args.checkpoints else self.args.checkpoints
        os.makedirs(path, exist_ok=True)

        train_steps = len(train_loader)
        early_stopping = EarlyStopping(patience=self.args.patience, verbose=True)
        model_optim = self._select_optimizer()
        criterion = self._select_criterion()
        
        if self.args.use_amp:
            scaler = torch.cuda.amp.GradScaler()
            
        scheduler = lr_scheduler.OneCycleLR(
            optimizer=model_optim,
            steps_per_epoch=train_steps,
            pct_start=self.args.pct_start,
            epochs=self.args.train_epochs,
            max_lr=self.args.learning_rate
        )

        if resume:
            latest_model_path = os.path.join(path, 'model_latest.pth')
            self.model.load_state_dict(torch.load(latest_model_path))
            print(f'Model loaded from {latest_model_path}')

        for epoch in range(self.args.train_epochs):
            iter_count = 0
            train_losses = []
            epoch_time = time.time()
            
            self.model.train()
            for i, (batch_x, batch_y, batch_x_mark, batch_y_mark, site, batch_x_ts, batch_y_ts) in enumerate(train_loader):
                iter_count += 1
                model_optim.zero_grad()
                
                batch_x = batch_x.float().to(self.device)
                batch_y = batch_y.float().to(self.device)
                batch_x_mark = batch_x_mark.float().to(self.device)
                batch_y_mark = batch_y_mark.float().to(self.device)
                
                dec_inp = torch.zeros_like(batch_y[:, -self.args.pred_len:, :]).float()
                dec_inp = torch.cat([batch_y[:, :self.args.label_len, :], dec_inp], dim=1).float().to(self.device)
                pretrain_flag = True if self.args.is_pretraining else False
                
                if self.args.use_amp:
                    with torch.cuda.amp.autocast():
                        if 'Linear' in self.args.model or 'TST' in self.args.model or self.args.model == 'LSTM':
                            outputs = self.model(batch_x, pretrain_flag)
                        else:
                            if self.args.output_attention:
                                outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)[0]
                            else:
                                outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)
                        
                        f_dim = -1 if self.args.features == 'MS' else 0
                        outputs = outputs[:, -self.args.pred_len:, f_dim:]
                        batch_y = batch_y[:, -self.args.pred_len:, f_dim:].to(self.device)
                        loss = criterion(outputs, batch_y)
                        
                    scaler.scale(loss).backward()
                    scaler.step(model_optim)
                    scaler.update()
                else:
                    if 'Linear' in self.args.model or 'TST' in self.args.model or self.args.model == 'LSTM':
                        outputs = self.model(batch_x, pretrain_flag)
                    else:
                        if self.args.output_attention:
                            outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)[0]
                        else:
                            outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)
                    
                    f_dim = -1 if self.args.features == 'MS' else 0
                    outputs = outputs[:, -self.args.pred_len:, f_dim:]
                    batch_y = batch_y[:, -self.args.pred_len:, f_dim:].to(self.device)
                    loss = criterion(outputs, batch_y)
                    
                    loss.backward()
                    model_optim.step()
                
                train_losses.append(loss.item())

                if (i + 1) % 100 == 0:
                    wandb.log({
                        "iteration": (epoch * len(train_loader)) + i + 1,
                        "train_loss_iteration": loss.item()
                    })
                    print(f"\titers: {i+1}, epoch: {epoch+1} | loss: {loss.item():.7f}")
                    speed = (time.time() - epoch_time) / iter_count
                    left_time = speed * ((self.args.train_epochs - epoch) * train_steps - i)
                    print(f'\tspeed: {speed:.4f}s/iter; left time: {left_time:.4f}s')
                    iter_count = 0
                    epoch_time = time.time()

                if self.args.lradj == 'TST':
                    adjust_learning_rate(model_optim, scheduler, epoch + 1, self.args, printout=False)
                    scheduler.step()
            
            print(f"Epoch: {epoch + 1} | cost time: {time.time() - epoch_time}")
            
            train_loss = np.average(train_losses)
            vali_loss = self.vali(vali_data, vali_loader, criterion)
            test_loss = self.vali(test_data, test_loader, criterion)
            
            print(f"Epoch: {epoch + 1} | Train Loss: {train_loss:.7f}, Vali Loss: {vali_loss:.7f}, Test Loss: {test_loss:.7f}")

            wandb.log({
                "epoch": epoch + 1,
                "train_loss": train_loss,
                "validation_loss": vali_loss,
                "test_loss": test_loss,
            })
            
            early_stopping(vali_loss, self.model, path)
            if early_stopping.early_stop:
                print("Early stopping triggered")
                break

            if self.args.lradj != 'TST':
                adjust_learning_rate(model_optim, scheduler, epoch + 1, self.args)
            else:
                print(f'Learning rate updated to {scheduler.get_last_lr()[0]}')
        
        best_model_path = os.path.join(path, 'checkpoint.pth')
        upload_files_to_wandb(
            project_name=self.project_name,
            run_name=self.run_name,
            model_weights_path=best_model_path
        )

        final_model_artifact = wandb.Artifact('final_model_weights', type='model')
        final_model_artifact.add_file(best_model_path)
        wandb.log_artifact(final_model_artifact)

        self.model.load_state_dict(torch.load(best_model_path))
        return self.model

    def vali(self, vali_data, vali_loader, criterion):
        total_loss = []
        self.model.eval()
        
        with torch.no_grad():
            for i, (batch_x, batch_y, batch_x_mark, batch_y_mark, site, batch_x_ts, batch_y_ts) in enumerate(vali_loader):
                batch_x = batch_x.float().to(self.device)
                batch_y = batch_y.float().to(self.device)
                batch_x_mark = batch_x_mark.float().to(self.device)
                batch_y_mark = batch_y_mark.float().to(self.device)
                
                dec_inp = torch.zeros_like(batch_y[:, -self.args.pred_len:, :]).float()
                dec_inp = torch.cat([batch_y[:, :self.args.label_len, :], dec_inp], dim=1).float().to(self.device)
                pretrain_flag = True if self.args.is_pretraining else False
                
                if self.args.use_amp:
                    with torch.cuda.amp.autocast():
                        if 'Linear' in self.args.model or 'TST' in self.args.model or self.args.model == 'LSTM':
                            outputs = self.model(batch_x, pretrain_flag)
                        else:
                            if self.args.output_attention:
                                outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)[0]
                            else:
                                outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)
                else:
                    if 'Linear' in self.args.model or 'TST' in self.args.model or self.args.model == 'LSTM':
                        outputs = self.model(batch_x, pretrain_flag)
                    else:
                        if self.args.output_attention:
                            outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)[0]
                        else:
                            outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)
                
                f_dim = -1 if self.args.features == 'MS' else 0
                outputs = outputs[:, -self.args.pred_len:, f_dim:]
                batch_y = batch_y[:, -self.args.pred_len:, f_dim:].to(self.device)
                
                loss = criterion(outputs, batch_y)
                total_loss.append(loss.item())
        
        self.model.train()
        return np.average(total_loss)

    def test(self, setting, model_path=None, test=0):
        test_data, test_loader = self._get_data(flag='test')
        
        if test:
            if model_path is not None:
                self.model.load_state_dict(torch.load(model_path))
            else:
                self.model.load_state_dict(torch.load(os.path.join('./checkpoints/', setting, 'checkpoint.pth')))
        
        folder_path = os.path.join('./test_results/', setting)
        os.makedirs(folder_path, exist_ok=True)
        
        evaluator = MetricEvaluator(file_path=os.path.join(folder_path, "site_metrics.txt"))
        
        pred_list = []
        true_list = []
        input_list = []
        
        self.model.eval()
        with torch.no_grad():
            for i, (batch_x, batch_y, batch_x_mark, batch_y_mark, site, batch_x_ts, batch_y_ts) in enumerate(test_loader):
                batch_x = batch_x.float().to(self.device)
                batch_y = batch_y.float().to(self.device)
                batch_x_mark = batch_x_mark.float().to(self.device)
                batch_y_mark = batch_y_mark.float().to(self.device)
                site = site.to(self.device)
                
                dec_inp = torch.zeros_like(batch_y[:, -self.args.pred_len:, :]).float()
                dec_inp = torch.cat([batch_y[:, :self.args.label_len, :], dec_inp], dim=1).float().to(self.device)
                pretrain_flag = True if self.args.is_pretraining else False
                
                if 'Linear' in self.args.model or 'TST' in self.args.model or self.args.model == 'LSTM':
                    outputs = self.model(batch_x, pretrain_flag)
                else:
                    if self.args.output_attention:
                        outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)[0]
                    else:
                        outputs = self.model(batch_x, batch_x_mark, dec_inp, batch_y_mark)
                
                f_dim = -1 if self.args.features == 'MS' else 0
                outputs = outputs[:, -self.args.pred_len:, f_dim:]
                batch_y = batch_y[:, -self.args.pred_len:, f_dim:].to(self.device)
                
                batch_x_np = batch_x.detach().cpu().numpy()
                outputs_np = outputs.detach().cpu().numpy()
                batch_y_np = batch_y.detach().cpu().numpy()
                
                pred = test_data.inverse_transform(site[:, 0], outputs_np.copy())
                true = test_data.inverse_transform(site[:, 0], batch_y_np.copy())
                
                evaluator.update(preds=outputs, targets=batch_y)
                
                pred_list.append(pred)
                true_list.append(true)
                input_list.append(batch_x_np)
                
                if i % 3 == 0:
                    self.plot_predictions(i, batch_x_np[0], true[0], pred[0], folder_path)
        
        rmse, nrmse_range, nrmse_mean, mae, nmae, mape, r2 = evaluator.calculate_metrics()
        
        print('\nMetrics:')
        print(f'RMSE: {rmse:.4f}')
        print(f'NRMSE (Range): {nrmse_range:.4f}')
        print(f'NRMSE (Mean): {nrmse_mean:.4f}')
        print(f'MAE: {mae:.4f}')
        print(f'NMAE: {nmae:.4f}')
        print(f'MAPE: {mape:.4f}')
        print(f'R2: {r2:.4f}')   


    def plot_predictions(self, i, input_sequence, ground_truth, predictions, save_path):
        """
        예측 시각화 함수 (인덱스 기반, 시각적 개선)
        Args:
            input_sequence (numpy array): 입력 시퀀스 데이터
            ground_truth (numpy array): 실제값
            predictions (numpy array): 예측값
            save_path (str): 플롯을 저장할 경로
        """
        # 인덱스 기반으로 x축을 설정
        input_index = np.arange(len(input_sequence))
        
        # ground_truth와 predictions에 input_sequence의 마지막 값을 앞에 추가하여 연결
        ground_truth = np.insert(ground_truth, 0, input_sequence[-1])
        predictions = np.insert(predictions, 0, input_sequence[-1])
        
        ground_truth_index = np.arange(len(input_sequence) - 1, len(input_sequence) + len(ground_truth) - 1)
        predictions_index = np.arange(len(input_sequence) - 1, len(input_sequence) + len(predictions) - 1)

        plt.figure(figsize=(14, 8))  # 더 큰 크기로 설정하여 가독성 향상

        # 입력 시퀀스의 마지막 5개 데이터만 플롯 (점선과 작은 점 추가, 투명도 적용)
        plt.plot(input_index[-10:], input_sequence.squeeze()[-10:], label='Input Sequence', color='royalblue', linestyle='--', alpha=0.7)
        plt.scatter(input_index[-10:], input_sequence.squeeze()[-10:], color='royalblue', s=10, alpha=0.6)

        # 수정된 ground_truth 사용하여 실제값 플롯 (굵기와 투명도 적용)
        plt.plot(ground_truth_index, ground_truth.squeeze(), label='Ground Truth', color='green', linewidth=2, alpha=0.8)
        
        # 예측값 플롯 (굵기와 투명도 적용)
        plt.plot(predictions_index, predictions.squeeze(), label='Predictions', color='red', linewidth=2, alpha=0.8)

        # 레이블, 제목 설정
        plt.xlabel('Index', fontsize=12)
        plt.ylabel('Value', fontsize=12)
        plt.title('Prediction vs Ground Truth', fontsize=14)
        
        # 레전드를 오른쪽 상단에 고정
        plt.legend(loc='upper right', fontsize=10)
        
        # Grid 추가
        plt.grid(color='gray', linestyle='--', linewidth=0.5, alpha=0.7)

        # 플롯 저장
        os.makedirs(save_path, exist_ok=True)
        plt.savefig(os.path.join(save_path, f'pred_{i}.png'))
        plt.close()    # def plot_predictions(self, i, input_sequence, ground_truth, predictions, save_path):
    #     """
    #     예측 시각화 함수 (인덱스 기반)
    #     Args:
    #         input_sequence (numpy array): 입력 시퀀스 데이터
    #         ground_truth (numpy array): 실제값
    #         predictions (numpy array): 예측값
    #         save_path (str): 플롯을 저장할 경로
    #     """
    #     # 인덱스 기반으로 x축을 설정
    #     input_index = np.arange(len(input_sequence))
        
    #     # ground_truth와 predictions에 input_sequence의 마지막 값을 앞에 추가하여 연결
    #     ground_truth = np.insert(ground_truth, 0, input_sequence[-1])
    #     predictions = np.insert(predictions, 0, input_sequence[-1])
    #     ground_truth_index = np.arange(len(input_sequence) - 1, len(input_sequence) + len(ground_truth) - 1)
        
    #     predictions_index = np.arange(len(input_sequence) -1, len(input_sequence) + len(predictions)-1)

    #     plt.figure(figsize=(12, 6))

    #     # 입력 시퀀스 플롯
    #     plt.plot(input_index, input_sequence.squeeze(), label='Input Sequence', color='blue', linestyle='--')
        
    #     # 수정된 ground_truth 사용하여 실제값 플롯
    #     plt.plot(ground_truth_index, ground_truth.squeeze(), label='Ground Truth', color='green')
        
    #     # 예측값 플롯
    #     plt.plot(predictions_index, predictions.squeeze(), label='Predictions', color='red')

    #     # 레이블, 제목 설정
    #     plt.xlabel('Index')
    #     plt.ylabel('Value')
    #     plt.title('Prediction vs Ground Truth')
        
    #     # 레전드를 오른쪽 상단에 고정
    #     plt.legend(loc='upper right')

    #     # 플롯 저장
    #     os.makedirs(save_path, exist_ok=True)
    #     plt.savefig(os.path.join(save_path, f'pred_{i}.png'))
    #     plt.close()   
    def predict(self, setting, load=False):
        pred_data, pred_loader = self._get_data(flag='pred')

        if load:
            path = os.path.join(self.args.checkpoints, setting)
            best_model_path = os.path.join(path, 'checkpoint.pth')
            self.model.load_state_dict(torch.load(best_model_path))

        pred_list = []

        self.model.eval()
        with torch.no_grad():
            for i, data in enumerate(pred_loader):

                batch_x, batch_y, batch_x_mark, batch_y_mark = data
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
                
                pred = outputs.detach().cpu().numpy()  # .squeeze()
                pred_list.append(pred)
                

        pred_np = np.array(pred_list)
        pred_np = pred_np.reshape(-1, pred_np.shape[-2], pred_np.shape[-1])

        # result save
        folder_path = os.path.join('./results/', setting)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        np_save_path = os.path.join(folder_path, "real_prediction_source.npy", pred_np)
        np.save(np_save_path)

        return
