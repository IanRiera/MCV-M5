#!/usr/bin/env python
# coding: utf-8
import torch
from torch import nn
from torch.utils.data import DataLoader
from torch.utils.tensorboard import SummaryWriter
from torchvision import datasets, transforms
from torchvision.utils import make_grid
from torchsummary import summary
from pathlib import Path
import os, sys, argparse
from tqdm import tqdm
from tqdm.contrib import tenumerate

def conv(ni, nf, ks=3, stride=1, padding=1, **kwargs):
    _conv = nn.Conv2d(ni, nf, kernel_size=ks, stride=stride, padding=padding,bias=False,**kwargs)
    nn.init.kaiming_normal_(_conv.weight)
    return _conv

def block(ni, nf): 
    _conv = conv(ni, nf, ks=3, stride=2, padding=1)
    return nn.Sequential(_conv, nn.BatchNorm2d(nf), nn.ReLU())

def get_model():
    return nn.Sequential(
        block(3, 32),
        block(32, 64),
        block(64, 128),
        block(128, 256),
        nn.AdaptiveAvgPool2d(1),
        nn.Flatten(),
        nn.Linear(256, 8))

def get_dataloaders(path:Path, img_size:int, batch_size:int, num_workers:int):
    """
    Get train and test dataloaders
    """

    # configure data transforms for trainig and testing
    train_transform = transforms.Compose([
                        transforms.Resize((img_size, img_size)),
                        transforms.ToTensor(),
                        transforms.Normalize(mean = [0.4273, 0.4523, 0.4497],
                                            std = [0.4273, 0.4523, 0.4497])])

    test_transform = transforms.Compose([
                        transforms.Resize((img_size, img_size)),
                        transforms.ToTensor(),
                        transforms.Normalize(mean = [0.4273, 0.4523, 0.4497],
                                            std = [0.4273, 0.4523, 0.4497])])

    # prepare datasets
    train_data = datasets.ImageFolder(path/'train', transform = train_transform)
    test_data = datasets.ImageFolder(path/'test', transform = test_transform)

    # prepare dataloaders
    train_loader = DataLoader(train_data, batch_size = batch_size, shuffle=True, num_workers=num_workers)
    test_loader = DataLoader(test_data, batch_size = batch_size, shuffle=False, num_workers=num_workers)

    return train_loader, test_loader

def parse_args(args = sys.argv[1:]):
    """
    Utility function for parsing command line arguments
    """
    parser = argparse.ArgumentParser(description='A simple script for training an image classifier')
    parser.add_argument('--exp_name',type=str,default='baseline',help='name of experiment')
    parser.add_argument("--data_path", default="/home/adityassrana/datatmp/Datasets/MIT_split", help = "path to MITSplit Dataset")
    parser.add_argument("--max_epochs", type=int, default=5, help="number of epochs to train our models for")
    parser.add_argument("--lr", type=float, default=1e-3, help="base learning rate")
    parser.add_argument("--image_size", type=int, default=64, help="image size for training")
    parser.add_argument("--batch_size", type=int, default=32, help="batch size for training")
    parser.add_argument("--num_workers", type=int, default=4, help="number of workers for loading data")
    parser.add_argument("--save_model", action="store_true", help = "to save the model at the end of each epoch")
    parser.add_argument("--tb", action="store_true", help = "to write to tensorboard")
    args = parser.parse_args(args)
    return args

if __name__ == '__main__':

    # parse command line arguments
    args = parse_args()
    print(args)

    # check for CUDA availabilitu
    if torch.cuda.is_available():
        print('CUDA is available, setting device to CUDA')
    # set device to  CUDA for training
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # get dataloaders
    train_loader, test_loader = get_dataloaders(Path(args.data_path), args.image_size, args.batch_size, args.num_workers)
    print('Dataloaders ready')

    # get training model and plot summary
    model = get_model()
    #summary(model, (3, args.image_size, args.image_size), device='cpu')
    # send model to GPU
    model.to(device)

    # get loss function and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr = args.lr)

    # Setup Tensorboard
    # We're uisng two writers to visualiz train and test results together
    if args.tb:
        writer_train = SummaryWriter(f'tb/{args.exp_name}/train')
        writer_test = SummaryWriter(f'tb/{args.exp_name}/test')

    # Training and Testing Loop
    for epoch in range(args.max_epochs):
        model.train()

        # training statistics
        losses, acc, count = [],[],[]
        for batch_idx, (xb,yb) in enumerate((train_loader)):
            #transfer data to GPU
            xb, yb = xb.to(device), yb.to(device)
            preds = model(xb)
            loss = criterion(preds, yb)
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()

            # calculating this way to account for the fact that the
            # last batch may have different batch size
            bs = xb.shape[0]
            # get number of right predictions
            correct_predictions = (preds.argmax(dim=1)==yb).float().sum()
            # add to list
            losses.append(bs*loss.item()), count.append(bs), acc.append(correct_predictions)

            # tensorboard
            if args.tb:
                writer_train.add_scalar('per_batch/train_loss', loss.item(), epoch*len(train_loader) + batch_idx)

        # accumulate/average statistics
        n = sum(count)
        train_loss_epoch = sum(losses)/n
        train_acc_epoch = sum(acc)/n

        if args.tb:    
            # write to tensorboard
            writer_train.add_scalar('per_epoch/losses',train_loss_epoch, epoch)
            writer_train.add_scalar('per_epoch/accuracy',train_acc_epoch, epoch)

        model.eval()
        with torch.no_grad():
            losses, acc, count = [],[],[]
            for batch_idx, (xb,yb) in enumerate((test_loader)):
                #transfer data to GPU
                xb,yb = xb.to(device), yb.to(device)
                preds = model(xb)
                loss = criterion(preds, yb)
                bs = xb.shape[0]
                # get number of right predictions
                correct_predictions = (preds.argmax(dim=1)==yb).float().sum()
                # add to list
                losses.append(bs*loss.item()), count.append(bs), acc.append(correct_predictions)
                
                if args.tb:
                    writer_test.add_scalar('per_batch/test_loss', loss.item(), epoch*len(test_loader) + batch_idx)

        # accumulate/average statistics
        n = sum(count)
        test_loss_epoch = sum(losses)/n
        test_acc_epoch = sum(acc)/n
        
        if args.tb:
            # write to tensorboard
            writer_test.add_scalar('per_epoch/losses', test_loss_epoch, epoch)
            writer_test.add_scalar('per_epoch/accuracy', test_acc_epoch, epoch)
    
        print(f"Epoch{epoch}, train_accuracy:{train_acc_epoch:.4f}, test_accuracy:{test_acc_epoch:.4f}, train_loss:{train_loss_epoch:.4f}, test_loss:{test_loss_epoch:.4f}")

        if args.save_model:
            torch.save(model.state_dict(),f"{args.exp_name}_epoch{epoch}_acc{train_acc_epoch:.4f}")
print("Finished training")