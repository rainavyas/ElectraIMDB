'''
Train an Electra-based classifer on the IMDB dataset
'''

import torch
import torch.nn as nn
from torch.utils.data import TensorDataset
from torch.utils.data import DataLoader
from transformers import ElectraTokenizer
from data_prep import get_train, get_test
import sys
import os
import argparse
from tools import AverageMeter, accuracy_topk, get_default_device
from models import SequenceClassifier

def train(train_loader, model, criterion, optimizer, epoch, device, print_freq=25):
    '''
    Run one train epoch
    '''
    losses = AverageMeter()
    accs = AverageMeter()

    # switch to train mode
    model.train()

    for i, (id, mask, target) in enumerate(train_loader):

        id = id.to(device)
        mask = mask.to(device)
        target = target.to(device)

        # Forward pass
        logits = model(id, mask)
        loss = criterion(logits, target)

        # Backward pass and update
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        # measure accuracy and record loss
        acc = accuracy_topk(logits.data, target)
        accs.update(acc.item(), id.size(0))
        losses.update(loss.item(), id.size(0))

        if i % print_freq == 0:
            print('Epoch: [{0}][{1}/{2}]\t'
                    'Loss {loss.val:.4f} ({loss.avg:.4f})\t'
                    'Accuracy {prec.val:.3f} ({prec.avg:.3f})'.format(
                      epoch, i, len(train_loader),
                      loss=losses, prec=accs))

def eval(val_loader, model, criterion, device):
    '''
    Run evaluation
    '''
    losses = AverageMeter()
    accs = AverageMeter()

    # switch to eval mode
    model.eval()

    with torch.no_grad():
        for i, (id, mask, target) in enumerate(val_loader):

            id = id.to(device)
            mask = mask.to(device)
            target = target.to(device)

            # Forward pass
            logits = model(id, mask)
            loss = criterion(logits, target)

            # measure accuracy and record loss
            acc = accuracy_topk(logits.data, target)
            accs.update(acc.item(), id.size(0))
            losses.update(loss.item(), id.size(0))

    print('Test\t Loss ({loss.avg:.4f})\t'
            'Accuracy ({prec.avg:.3f})\n'.format(
              loss=losses, prec=accs))

if __name__ == "__main__":

    # Get command line arguments
    commandLineParser = argparse.ArgumentParser()
    commandLineParser.add_argument('OUT', type=str, help='Specify output th file')
    commandLineParser.add_argument('--B', type=int, default=16, help="Specify batch size")
    commandLineParser.add_argument('--epochs', type=int, default=2, help="Specify epochs")
    commandLineParser.add_argument('--lr', type=float, default=0.000001, help="Specify learning rate")
    commandLineParser.add_argument('--sch', type=int, default=10, help="Specify scheduler rate")
    commandLineParser.add_argument('--seed', type=int, default=1, help="Specify seed")

    args = commandLineParser.parse_args()
    out_file = args.OUT
    batch_size = args.B
    epochs = args.epochs
    lr = args.lr
    sch = args.sch
    seed = args.seed

    torch.manual_seed(seed)

    # Save the command run
    if not os.path.isdir('CMDs'):
        os.mkdir('CMDs')
    with open('CMDs/train.cmd', 'a') as f:
        f.write(' '.join(sys.argv)+'\n')

    # Get the device
    device = get_default_device()

    # Load the data as tensors
    input_ids_train, mask_train, labels_train = get_train()
    input_ids_val, mask_val, labels_val = get_test()

    # Use dataloader to handle batches
    train_ds = TensorDataset(input_ids_train, mask_train, labels_train)
    val_ds = TensorDataset(input_ids_val, mask_val, labels_val)

    train_dl = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_dl = DataLoader(val_ds, batch_size=batch_size)

    # Initialise classifier
    model = SequenceClassifier()
    model.to(device)

    # Optimizer
    optimizer = torch.optim.SGD(model.parameters(), lr=lr, momentum=0.9, nesterov=True)

    # Scheduler
    scheduler = torch.optim.lr_scheduler.MultiStepLR(optimizer, milestones=[sch])

    # Criterion
    criterion = nn.CrossEntropyLoss().to(device)

    # Train
    for epoch in range(epochs):

        # train for one epoch
        print('current lr {:.5e}'.format(optimizer.param_groups[0]['lr']))
        train(train_dl, model, criterion, optimizer, epoch, device)
        scheduler.step()

        # evaluate on validation set
        eval(val_dl, model, criterion, device)

# Save the trained model
state = model.state_dict()
torch.save(state, out_file)
