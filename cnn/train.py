import os
import sys
import glob
import numpy as np
import torch
import utils
import argparse
import genotypes
import time
import torch.nn as nn
import torch.utils
import torchvision.datasets as dset
import torch.backends.cudnn as cudnn
from logger import get_logger
from model import NetworkCIFAR as Network

parser = argparse.ArgumentParser("cifar")
parser.add_argument('--data', type=str, default='../../Data', help='location of the data corpus')
parser.add_argument('--dataset', type=str, default='cifar', help='name of the dataset')
parser.add_argument('--batch_size', type=int, default=72, help='batch size')
parser.add_argument('--learning_rate', type=float, default=0.025, help='init learning rate')
parser.add_argument('--momentum', type=float, default=0.9, help='momentum')
parser.add_argument('--weight_decay', type=float, default=3e-4, help='weight decay')
parser.add_argument('--report_freq', type=float, default=50, help='report frequency')
parser.add_argument('--gpu', type=int, default=0, help='gpu device id')
parser.add_argument('--epochs', type=int, default=600, help='num of training epochs')
parser.add_argument('--init_channels', type=int, default=36, help='num of init channels')
parser.add_argument('--layers', type=int, default=20, help='total number of layers')
parser.add_argument('--model_path', type=str, help='path to save the model')
parser.add_argument('--auxiliary', action='store_true', default=False, help='use auxiliary tower')
parser.add_argument('--auxiliary_weight', type=float, default=0.4, help='weight for auxiliary loss')
parser.add_argument('--cutout', action='store_true', default=False, help='use cutout')
parser.add_argument('--cutout_length', type=int, default=16, help='cutout length')
parser.add_argument('--drop_path_prob', type=float, default=0.2, help='drop path probability')
parser.add_argument('--save', type=str, default='EXP', help='experiment name')
parser.add_argument('--seed', type=int, default=0, help='random seed')
parser.add_argument('--arch', type=str, default='DARTS', help='which architecture to use')
parser.add_argument('--grad_clip', type=float, default=5, help='gradient clipping')
args = parser.parse_args()

CIFAR_CLASSES = 10


def main():
    if not torch.cuda.is_available():
        logger.info('no gpu device available')
        sys.exit(1)

    np.random.seed(args.seed)
    torch.cuda.set_device(args.gpu)
    cudnn.benchmark = True
    torch.manual_seed(args.seed)
    cudnn.enabled = True
    torch.cuda.manual_seed(args.seed)
    logger.info('gpu device = %d' % args.gpu)
    logger.info("args = %s", args)
    
    CIFAR_CLASSES = 10
    MNIST_CLASSES = 10
    FMNIST_CLASSES = 10
    CLASSES = CIFAR_CLASSES
    train_transform, valid_transform = utils._data_transforms_cifar10(args)
    TARGET_DATASET_TRAIN = dset.CIFAR10(root=args.data, train=True, download=True, transform=train_transform)
    TARGET_DATASET_VALID = dset.CIFAR10(root=args.data, train=False, download=True, transform=valid_transform)

    if args.dataset == 'cifar': 
        CLASSES = CIFAR_CLASSES
        train_transform, valid_transform = utils._data_transforms_cifar10(args)
        TARGET_DATASET_TRAIN = dset.CIFAR10(root=args.data, train=True, download=True, transform=train_transform)
        TARGET_DATASET_VALID = dset.CIFAR10(root=args.data, train=False, download=True, transform=valid_transform)
    elif args.dataset == 'mnist': 
        CLASSES = MNIST_CLASSES
        train_transform, valid_transform = utils._data_transforms_cifar10(args)
        TARGET_DATASET_TRAIN = dset.MNIST(root=args.data, train=True, download=True, transform=train_transform)
        TARGET_DATASET_VALID = dset.MNIST(root=args.data, train=False, download=True, transform=valid_transform)
    elif args.dataset == 'fmnist': 
        CLASSES = FMNIST_CLASSES
        train_transform, valid_transform = utils._data_transforms_cifar10(args)
        TARGET_DATASET_TRAIN = dset.FashionMNIST(root=args.data, train=True, download=True, transform=train_transform)
        TARGET_DATASET_VALID = dset.FashionMNIST(root=args.data, train=False, download=True, transform=valid_transform)


    genotype = eval("genotypes.%s" % args.arch)
    model = Network(args.init_channels, CIFAR_CLASSES, args.layers, args.auxiliary, genotype)
    model = model.cuda()

    if args.model_path is not None:
        utils.load(model, args.model_path)

    logger.info("param size = %fMB", utils.count_parameters_in_MB(model))

    criterion = nn.CrossEntropyLoss().cuda()
    optimizer = torch.optim.SGD(
        model.parameters(),
        args.learning_rate,
        momentum=args.momentum,
        weight_decay=args.weight_decay
    )
    
    #train_transform, valid_transform = utils._data_transforms_cifar10(args)
    train_data = TARGET_DATASET_TRAIN
    valid_data = TARGET_DATASET_VALID

    train_queue = torch.utils.data.DataLoader(
        train_data, batch_size=args.batch_size, shuffle=True, pin_memory=True, num_workers=6)
    valid_queue = torch.utils.data.DataLoader(
        valid_data, batch_size=args.batch_size, shuffle=False, pin_memory=True, num_workers=6)

    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, float(args.epochs))
    for epoch in range(args.epochs):
        scheduler.step()
        logger.info('epoch %d lr %e', epoch, scheduler.get_lr()[0])
        model.drop_path_prob = args.drop_path_prob * epoch / args.epochs
        train_acc, train_obj = train(train_queue, model, criterion, optimizer)
        logger.info('train_acc %f', train_acc)
        valid_acc, valid_obj = infer(valid_queue, model, criterion)
        logger.info('valid_acc %f', valid_acc)
        torch.cuda.empty_cache()
        utils.save(model, os.path.join(args.save, 'weights.pt'))


def train(train_queue, model, criterion, optimizer):
    objs = utils.AvgrageMeter()
    top1 = utils.AvgrageMeter()
    top5 = utils.AvgrageMeter()
    model.train()
    for step, (input, target) in enumerate(train_queue):
        input = input.cuda()
        target = target.cuda(async=True)
        optimizer.zero_grad()
        logits, logits_aux = model(input)
        loss = criterion(logits, target)
        #if args.auxiliary:
        #    loss_aux = criterion(logits_aux, target)
        #    loss += args.auxiliary_weight * loss_aux
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
        optimizer.step()

        prec1, prec5 = utils.accuracy(logits, target, topk=(1, 5))
        n = input.size(0)
        objs.update(loss.item(), n)
        top1.update(prec1.item(), n)
        top5.update(prec5.item(), n)

        if step % args.report_freq == 0:
            logger.info('train %03d %e %f %f', step, objs.avg, top1.avg, top5.avg)

    return top1.avg, objs.avg


def infer(valid_queue, model, criterion):
    objs = utils.AvgrageMeter()
    top1 = utils.AvgrageMeter()
    top5 = utils.AvgrageMeter()
    model.eval()
    with torch.set_grad_enabled(False):
        for step, (input, target) in enumerate(valid_queue):
            input = input.cuda()
            target = target.cuda(async=True)
            logits, _ = model(input)
            loss = criterion(logits, target)
            prec1, prec5 = utils.accuracy(logits, target, topk=(1, 5))
            n = input.size(0)
            objs.update(loss.item(), n)
            top1.update(prec1.item(), n)
            top5.update(prec5.item(), n)

            if step % args.report_freq == 0:
                logger.info('valid %03d %e %f %f', step, objs.avg, top1.avg, top5.avg)

    return top1.avg, objs.avg


if __name__ == '__main__':
    args.save = 'eval-{}-{}'.format(args.save, time.strftime("%Y%m%d-%H%M%S"))
    utils.create_exp_dir(args.save, scripts_to_save=glob.glob('*.py'))
    logger = get_logger(__name__, b'INFO', filename=args.save + "\\log.log")
    main()
