import os
import pandas as pd

def generate_csv_mapping(input_directory, output_csv, dataset_name="DKASC"):
    """
    Reads all CSV files in the specified directory and generates a new CSV file
    mapping original filenames to renamed filenames in the required format.

    Args:
    - input_directory (str): Path to the directory containing the CSV files.
    - output_csv (str): Path to save the generated CSV file.
    - dataset_name (str): Dataset name to include in the output (default: DKASC).
    """
    # Get all CSV files in the directory
    csv_files = [f for f in os.listdir(input_directory) if f.endswith('.csv')]
    
    # Sort files to ensure consistent indexing
    csv_files.sort()
    
    # Prepare data for the new CSV
    data = []
    for idx, file in enumerate(csv_files, start=1):
        # Generate new filename with the index
        new_filename = f"{idx:02d}_{file}"
        data.append([dataset_name, file, new_filename])
    
    # Create a DataFrame
    df = pd.DataFrame(data, columns=["dataset", "original_name", "mapping_name"])
    
    # Save to a CSV file
    df.to_csv(output_csv, index=False)
    print(f"CSV mapping saved to {output_csv}")

# Example usage
input_directory = "/ailab_mat/dataset/PV/DKASC/processed_data_all"  # Replace with your directory
save_dicrectory = "/home/bak/Projects/PatchTST/data_provider/DKASC_mapping"
os.makedirs(save_dicrectory, exist_ok=True)
output_csv = os.path.join(save_dicrectory, "mapping.csv")

generate_csv_mapping(input_directory, output_csv)