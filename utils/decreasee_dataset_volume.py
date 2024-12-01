import os
import pandas as pd
from glob import glob
from tqdm import tqdm


# Directory containing the CSV files
dataset_name = 'Source' # DKASC_AliceSprings, DKASC_Yulara, Germany, GIST, Miryang, OEDI_California, OEDI_Georgia, UK

directory = f'/ailab_mat/dataset/PV/{dataset_name}/processed_data_day/'

# Find all files ending with '.csv'
csv_files = glob(os.path.join(directory, '*.csv'))

# Initialize a list to store processed DataFrames
processed_data = []

# Set the reduction factor (e.g., 1/8 or 1/16)
reduction_factor = 8  # Change to 16 for 1/16

# Loop through each CSV file
for file in tqdm(csv_files, desc='Processing files'):
    # Load the data
    data = pd.read_csv(file)
    
    # Convert 'timestamp' to datetime if it exists
    if 'timestamp' in data.columns:
        data['timestamp'] = pd.to_datetime(data['timestamp'])
        # Sort by timestamp
        data = data.sort_values(by='timestamp')
    
    # Keep recent rows while downsampling
    reduced_data = data.iloc[-len(data) // reduction_factor:]
    
    # Store the reduced DataFrame
    processed_data.append(reduced_data)
    
    # Optional: Save the reduced file
    output_path = file.replace('processed_data_day', f'processed_data_day_reduced_{reduction_factor}')
    output_dir = os.path.dirname(output_path)

    # 디렉토리가 없으면 생성
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    reduced_data.to_csv(output_path, index=False)