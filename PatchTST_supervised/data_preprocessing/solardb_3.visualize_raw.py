import os
import numpy as np
import pandas as pd
import warnings
import datetime
from dateutil.relativedelta import relativedelta
import matplotlib.pyplot as plt

warnings.filterwarnings('ignore')




if __name__ == '__main__':
    root_path = './dataset/SolarDB/pre-process'

    ##             power_ac / temp / humidity / sun_irradiance
    palette = ['', 'limegreen', 'orange', 'dodgerblue', 'red']
    unit    = ['', '[W]', '[°C]', '[%]', '[W/m²]']
    
    for i in range(1, 17):
        if i != 8: continue
        pp = f'pp{i}'
        print('='*30)
        vis_path = f'visualize/SolarDB/raw/{pp}'
        os.makedirs(vis_path, exist_ok=True)

        ## read raw data
        df = pd.read_csv(os.path.join(root_path, f'{pp}_year.csv'))
        print(pp, 'null', df.isnull().sum().sum())

        ## get mean & std of each variable
        _mean, _std = [''], ['']
        _mean.extend(df.loc[:, df.columns[1:]].mean().tolist())
        _std.extend(df.loc[:, df.columns[1:]].std().tolist())

        ## get start & finish date
        _start_date     = df.loc[0, 'timestamp'].split(' ')[0]
        year,month,day  = list(map(int, _start_date.split('-')))
        date            = datetime.datetime(year, month, day)

        _finish_date    = df.loc[len(df)-1, 'timestamp'].split(' ')[0]
        year,month,day  = list(map(int, _finish_date.split('-')))
        finish_date     = datetime.datetime(year, month, day)

        while True:
            last_date   = date + datetime.timedelta(days=7)
            _first_date = f'{date.year}-{str(date.month).zfill(2)}-{str(date.day).zfill(2)}'
            _last_date  = f'{last_date.year}-{str(last_date.month).zfill(2)}-{str(last_date.day).zfill(2)}'
            
            first_idx   = df[(f'{_first_date} 00:00:00' <= df['timestamp'])].index[0]
            last_idx    = df[(f'{_last_date} 00:00:00' > df['timestamp'])].index[-1]

            _hour       = df.loc[first_idx:last_idx, 'timestamp'].apply(lambda x: x.split(':')[0][5:])      # if ' 00' in x or ' 12' in x else ' '

            ## visualize graph per variable
            for j, column in enumerate(df.columns):
                if column == 'timestamp': continue

                _values = df.loc[first_idx:last_idx, column]

                plt.clf()
                fig = plt.figure(figsize=(20,9))
                ax = fig.add_subplot(1, 1, 1)
                ax.set_title(f'{_first_date} ~ {_last_date}   {column} {unit[j]}')
                ax.grid(True, linestyle=':', axis='x')

                ax.plot(_hour, _values, label=f'{column} {unit[j]}', color=palette[j])
                ax.set_xticks([k for k in range(0, 7*24+1,12)])
                ax.set_xlabel(f'mean: {round(df.loc[first_idx:last_idx, column].mean(), 2)}\nstd: {round(df.loc[first_idx:last_idx, column].std(), 2)}')
                
                plt.legend()
                plt.savefig(f'{vis_path}/{_first_date}-{_last_date}_{column}.png', bbox_inches='tight', pad_inches=0.3)

                
            ## visualize graph of all standardized variables
            plt.clf()
            fig = plt.figure(figsize=(20,9))
            ax = fig.add_subplot(1, 1, 1)
            ax.set_title(f'{_first_date} ~ {_last_date}   All variables standardized')
            ax.grid(True, linestyle=':', axis='x')

            for j, column in enumerate(df.columns):
                if column == 'timestamp': continue

                _values = df.loc[first_idx:last_idx, column]

                ax.plot(_hour, (_values - _mean[j]) / _std[j], label=f'{column} {unit[j]}', color=palette[j])
                ax.set_xticks([k for k in range(0, 7*24+1,12)])

            plt.legend()
            plt.savefig(f'{vis_path}/{_first_date}-{_last_date}_all.png', bbox_inches='tight', pad_inches=0.3)

            ## forward a month
            date += relativedelta(months=1)
            if date > finish_date: break


        ## visualize graph of all standardized variables for a year
        plt.clf()

        fig = plt.figure(figsize=(100, 45))

        ax_tem = fig.add_subplot(4,1,1)
        ax_tem.set_title(f'{_start_date} ~ {_finish_date}   All variables standardized')
        ax_tem.grid(True, linestyle=':', axis='x')

        ax_hum = fig.add_subplot(4, 1, 2)
        ax_hum.set_title(f'{_start_date} ~ {_finish_date}   All variables standardized')
        ax_hum.grid(True, linestyle=':', axis='x')

        ax_irr = fig.add_subplot(4, 1, 3)
        ax_irr.set_title(f'{_start_date} ~ {_finish_date}   All variables standardized')
        ax_irr.grid(True, linestyle=':', axis='x')

        ax_all = fig.add_subplot(4, 1, 4)
        ax_all.set_title(f'{_start_date} ~ {_finish_date}   All variables standardized')
        ax_all.grid(True, linestyle=':', axis='x')

        _hour = df.loc[:, 'timestamp'].apply(lambda x: x.split(':')[0][5:])      # if ' 00' in x or ' 12' in x else ' '

        for j, column in enumerate(df.columns):
            if column == 'timestamp': continue

            _values = df.loc[:, column]

            if column in ['power_ac', 'temp']:
                ax_tem.plot(_hour, (_values - _mean[j]) / _std[j], label=f'{column} {unit[j]}', color=palette[j])
                ax_tem.set_xticks([k for k in range(348, 8760, 732)])
            
            if column in ['power_ac', 'humidity']:
                ax_hum.plot(_hour, (_values - _mean[j]) / _std[j], label=f'{column} {unit[j]}', color=palette[j])
                ax_hum.set_xticks([k for k in range(348, 8760, 732)])

            if column in ['power_ac', 'sun_irradiance']:
                ax_irr.plot(_hour, (_values - _mean[j]) / _std[j], label=f'{column} {unit[j]}', color=palette[j])
                ax_irr.set_xticks([k for k in range(348, 8760, 732)])

            ax_all.plot(_hour, (_values - _mean[j]) / _std[j], label=f'{column} {unit[j]}', color=palette[j])
            ax_all.set_xticks([k for k in range(348, 8760, 732)])


        plt.legend()
        plt.savefig(f'{vis_path}/0_{_start_date}-{_finish_date}_all.png', bbox_inches='tight', pad_inches=0.3)




