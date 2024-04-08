import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

class Model(nn.Module):
    """
    Just one Linear layer
    """
    def __init__(self, configs):
        super(Model, self).__init__()
        self.input_dim = configs.input_dim
        self.hidden_dim = configs.hidden_dim
        self.num_layers = 2
        
        self.seq_len = configs.seq_len
        self.pred_len = configs.pred_len

        self.lstm = nn.LSTM(self.input_dim, self.hidden_dim, batch_first=True, num_layers=self.num_layers, bidirectional=configs.bidirectional)
        self.Linear = nn.Linear(self.seq_len, self.pred_len)
        # Use this line if you want to visualize the weights
        # self.Linear.weight = nn.Parameter((1/self.seq_len)*torch.ones([self.pred_len,self.seq_len]))

    def init_hidden(self, x):
        h0 = torch.zeros((self.num_layers * (2 if self.bidirectional else 1), x.size(0), self.hidden_dim)).cuda()
        c0 = torch.zeros((self.num_layers * (2 if self.bidirectional else 1), x.size(0), self.hidden_dim)).cuda()
        
        return h0, c0

    def forward(self, x):
        hidden = self.init_hidden(x)
        out, hidden = self.lstm(x, hidden)

        out_f = out[:, -1, :self.hidden_dim]
        out_b = out[:, 0, self.hidden_dim:]
        out = torch.cat((out_f, out_b), dim=1)
        out = self.Linear(out)

        return out

    
    
    # def forward(self, x):
    #     # x: [Batch, Input length, Channel]

    #     x = self.Linear(x.permute(0,2,1)).permute(0,2,1)
    #     return x # [Batch, Output length, Channel]
    
    # class PlainLSTM(nn.Module):
    #     def __init__(self, config, hidden_dim, num_classes):
    #         super(PlainLSTM, self).__init__()
    #         self.config = config
    #         self.hidden_dim = hidden_dim
    #         self.num_layers = 2
    #         self.num_classes = num_classes
    #         self.bidirectional = config['bidirectional']

    #         self.input_dim = 128

    #         # architecture
    #         self.lstm = nn.LSTM(self.input_dim, self.hidden_dim, batch_first=True, num_layers=self.num_layers, bidirectional=config['bidirectional'])
    #         self.fc = nn.Linear(self.hidden_dim * 2, 1)

    #     def init_hidden(self, x):
    #         h0 = torch.zeros((self.num_layers * (2 if self.bidirectional else 1), x.size(0), self.hidden_dim)).cuda()
    #         c0 = torch.zeros((self.num_layers * (2 if self.bidirectional else 1), x.size(0), self.hidden_dim)).cuda()
            
    #         return h0, c0

    #     def forward(self, x):
    #         hidden = self.init_hidden(x)
    #         out, hidden = self.lstm(x, hidden)

    #         out_f = out[:, -1, :self.hidden_dim]
    #         out_b = out[:, 0, self.hidden_dim:]
    #         out = torch.cat((out_f, out_b), dim=1)
    #         out = self.fc(out)

    #         return out
    
    # class MainModel(nn.Module):
    
    #     def __init__(self, config):

    #         super(MainModel, self).__init__()

    #         self.config = config
    #         self.feature = ResNetFeature(config)
    #         self.classifier = PlainLSTM(config, hidden_dim=config['hidden_dim'], num_classes=config['num_classes'])

    #     def forward(self, x):
    #         out = self.classifier(self.feature(x))

    #         return out