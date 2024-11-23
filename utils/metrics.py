import numpy as np
import torch
from torchmetrics import R2Score


# - RMSE [kW] 규모 별 평가
# - nRMSE [%]
# - MAE [kW] 규모 별 평가
# - nMAE [%]
# - MAPE [%]
# - MBE [kW] 규모 별 평가
# - R²
# - SS (transfer)


import numpy as np
import torch
from sklearn.metrics import r2_score

class MetricEvaluator:
    def __init__(self, file_path):
        self.file_path = file_path
        self.preds_list = []
        self.targets_list = []

    def update(self, preds, targets):
        """
        매 배치마다 전체 예측값과 실제값을 누적하여 사용
        """
        self.preds_list.append(preds.cpu().numpy())
        self.targets_list.append(targets.cpu().numpy())

    def calculate_metrics(self, preds, targets):
        """
        주어진 예측값과 실제값에 대한 지표 계산
        """
        mae = np.mean(np.abs(preds - targets))
        mse = np.mean((preds - targets) ** 2)
        rmse = np.sqrt(mse)

        # nRMSE (최대-최소 및 평균값 기준)
        targets_min = np.min(targets)
        targets_max = np.max(targets)
        targets_mean = np.mean(targets)

        nrmse_range = (rmse / (targets_max - targets_min)) * 100  # (최대-최소) 기준 nRMSE
        nrmse_mean = (rmse / targets_mean) * 100  # 평균 기준 nRMSE

        # nMAE 계산 (평균값 기준)
        nmae = (mae / targets_mean) * 100  # 평균 기준 nMAE

        # MAPE 계산
        mape = np.mean(np.abs((preds - targets) / targets)) * 100

        # R2 Score 계산
        r2 = r2_score(targets, preds)

        return rmse, nrmse_range, nrmse_mean, mae, nmae, mape, r2

    def evaluate(self, scale_groups):
        """
        전체 데이터에 대한 지표를 규모별로 계산하여 파일에 기록
        scale_groups: list of tuples [(scale_name, mask), ...]
        mask는 numpy 배열로 preds와 targets의 특정 요소를 필터링하는 조건을 나타냅니다.
        """
        preds = np.concatenate(self.preds_list)
        targets = np.concatenate(self.targets_list)

        results = []
        for scale_name, mask in scale_groups:
            masked_preds = preds[mask]
            masked_targets = targets[mask]

            if len(masked_preds) > 0:
                metrics = self.calculate_metrics(masked_preds, masked_targets)
                results.append((scale_name, metrics))

        # 결과를 파일에 기록
        with open(self.file_path, "w") as file:
            file.write("Scale-Specific Evaluation Metrics\n")
            file.write("=" * 50 + "\n")
            for scale_name, (rmse, nrmse_range, nrmse_mean, mae, nmae, mape, r2) in results:
                file.write(f"Scale: {scale_name}\n")
                file.write(f"RMSE: {rmse:.4f} kW\n")
                file.write(f"nRMSE (Range): {nrmse_range:.4f}%\n")
                file.write(f"nRMSE (Mean): {nrmse_mean:.4f}%\n")
                file.write(f"MAE: {mae:.4f} kW\n")
                file.write(f"nMAE: {nmae:.4f}%\n")
                file.write(f"MAPE: {mape:.4f}%\n")
                file.write(f"R2 Score: {r2:.4f}\n")
                file.write("=" * 50 + "\n")

        return results



def generate_scale_groups_for_dataset(dataset_type):
    if dataset_type == "Alice_Springs":
        return [
            ("Small", lambda preds, targets: targets < 30)
        ]

    elif dataset_type == "Yulara":
        return [
            ("Small", lambda preds, targets: (targets >= 0) & (targets < 30)),
            ("Small-Medium", lambda preds, targets: (targets >= 30) & (targets < 100)),
            ("100kW", lambda preds, targets: (targets >= 100) & (targets < 200)),
            ("200kW", lambda preds, targets: (targets >= 200) & (targets < 300)),
            ("1mW", lambda preds, targets: targets >= 1000)
        ]
    
    elif dataset_type == "GIST":
        return [
            ("Small", lambda preds, targets: (targets >= 0) & (targets < 30)),
            ("Small-Medium", lambda preds, targets: (targets >= 30) & (targets < 100)),
            ("100kW", lambda preds, targets: (targets >= 100) & (targets < 200)),
            ("200kW", lambda preds, targets: (targets >= 200) & (targets < 300))
        ]
    
    elif dataset_type == "Miryang":
        return [
            ("Small-Medium", lambda preds, targets: (targets >= 30) & (targets < 100)),
            ("600kW", lambda preds, targets: (targets >= 600) & (targets < 700)),
            ("900kW", lambda preds, targets: (targets >= 800) & (targets < 900))
        ]
    
    elif dataset_type == "California":
        return [
            ("700kW"), lambda preds, targets: (targets >= 700) & (targets < 800)
        ]
    elif dataset_type == "Georgia":
        return[
            ("3mW"), lambda preds, targets: (targets >= 3000) & (targets < 4000)
        ]
    elif dataset_type == "UK":
        return[
            ("Small"), lambda preds, targets: (targets >= 0) & (targets < 30)
        ]
    elif dataset_type == "German":
        return[
            ("Small"), lambda preds, targets: (targets >= 0) & (targets < 30)
        ]
    else:
        raise ValueError(f"Unknown dataset type: {dataset_type}")
    

# def Yulara_small(preds, targets):
#     return (targets >= 0) & (targets < 30)

# def Yulara_small_medium(preds, targets):
#     return (targets >= 30) & (targets < 100)

# def Yulara_100kW(preds, targets):
#     return (targets >= 100) & (targets < 200)

# def Yulara_200kW(preds, targets):
#     return (targets >= 200) & (targets < 300)

# def Yulara_1mW(preds, targets):
#     return targets >= 1000

# def GIST_small(preds, targets):
#     return (targets >= 0) & (targets < 30)

# def GIST_small_medium(preds, targets):
#     return (targets >= 30) & (targets < 100)

# def GIST_100kW(preds, targets):
#     return (targets >= 100) & (targets < 200)

# def GIST_200kW(preds, targets):
#     return (targets >= 200) & (targets < 300)

# def Miryang_small_medium(preds, targets):
#     return (targets >= 30) & (targets < 100)

# def Miryang_600kW(preds, targets):
#     return (targets >= 600) & (targets < 700)

# def Miryang_900kW(preds, targets):
#     return (targets >= 800) & (targets < 900)
