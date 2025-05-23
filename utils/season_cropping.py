import pandas as pd
import os

# Load the CSV file
season = 'Winter' # 'Spring', 'Summer', 'Autumn', 'Winter'
site_csv = '133.1_E03_GTI.csv' # 133.1_E03_GTI, 69.6_C10_Renewable-E-Bldg
# csv_dir_path = f'/home/bak/Projects/pv-power-forecasting/data/GIST_{season}/processed_data_all'
csv_dir_path = f'/home/bak/Projects/pv-power-forecasting/data/GIST/processed_data_all'
csv_path = os.path.join(csv_dir_path, site_csv)

df = pd.read_csv(csv_path)

# Convert the timestamp column to datetime
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Extract month information
df['month'] = df['timestamp'].dt.month

# Create month group mappings - you can customize these
month_groups = {
    # 'Spring': [3, 4, 5],
    # 'Summer': [6, 7, 8],
    # 'Autumn': [9, 10, 11],
    'Winter': [12, 1, 2]
}

# Create a new column for month groups
def assign_month_group(month):
    for group_name, months in month_groups.items():
        if month in months:
            return group_name
    return 'unknown'

df['month_group'] = df['month'].apply(assign_month_group)

# Now you can create separate dataframes for each group
for group_name, months in month_groups.items():
    group_df = df[df['month'].isin(months)]
    
    # Save to separate CSV if needed
    output_path = f'data/{group_name}_{site_csv}'
    group_df.to_csv(output_path, index=False)
    print(f"Created {group_name} dataset with {len(group_df)} records")
    
    # You can also analyze each group separately
    if len(group_df) > 0:
        avg_power = group_df['Active_Power'].mean()
        max_power = group_df['Active_Power'].max()
        print(f"  Average power: {avg_power:.2f} kW, Max power: {max_power:.2f} kW")