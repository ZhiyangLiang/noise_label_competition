# dataset - preparing data and adding label noise
from __future__ import print_function
import torch
from PIL import Image
import os
import os.path
import numpy as np
import sys

import pickle
import torch.utils.data as data
from torchvision.datasets.utils import download_url, check_integrity
import torchvision.transforms as transforms
import numpy as np
from torch.utils.data.sampler import SubsetRandomSampler
import argparse

# r: noise amount s: random seed
parser = argparse.ArgumentParser()
parser.add_argument('--opt1', type=int, required=True, help='category of noise dataset')
parser.add_argument('--opt2', type=int, required=True, help='category of noise label')
parser.add_argument('--opt3', type=int, required=True, help='category of alpha')
parser.add_argument('--s', type=int, default=10086, help='random seed')
parser.add_argument('--batchsize', type=int, default=128)
parser.add_argument('--bias', type=str, required=False)
parser.add_argument('--root', type=str, default="./datasets/CIFAR10/cifar-10-batches-py",
                    help='Path for loading CIFAR10 dataset')
args = parser.parse_args()
CUDA = True if torch.cuda.is_available() else False

Tensor = torch.cuda.FloatTensor if CUDA else torch.FloatTensor

# data root:
root = args.root
opt1 = args.opt1
opt2 = args.opt2
opt3 = args.opt3
batch_size = args.batchsize


class CIFAR10_(data.Dataset):
    base_folder = 'cifar-10-batches-py'
    url = "https://www.cs.toronto.edu/~kriz/cifar-10-python.tar.gz"
    filename = "cifar-10-python.tar.gz"
    tgz_md5 = 'c58f30108f718f92721af3b95e74349a'
    train_list = [
        ['data_batch_1', 'c99cafc152244af753f735de768cd75f'],
        ['data_batch_2', 'd4bba439e000b95fd0a9bffe97cbabec'],
        ['data_batch_3', '54ebc095f3ab1f0389bbae665268c751'],
        ['data_batch_4', '634d18415352ddfa80567beed471001a'],
    ]

    valid_list = [
        ['data_batch_5', '482c414d41f54cd18b22e5b47cb7c3cb'],
    ]

    test_list = [
        ['test_batch', '40351d587109b95175f43aff81a1287e'],
    ]
    meta = {
        'filename': 'batches.meta',
        'key': 'label_names',
        'md5': '5ff9c542aee3614f3951f8cda6e48888',
    }

    def __init__(self, root, noise_indices=[0, 1, 2, 3, 4, 5], train=True, valid=False, test=False, noisy=True,
                 transform=None, target_transform=None,
                 download=True):
        self.root = os.path.expanduser(root)
        self.transform = transform
        self.target_transform = target_transform
        self.noise_indices = noise_indices
        self.train = train  # training set or test set
        self.valid = valid
        self.test = test
        self.noisy = noisy

        if download:
            self.download()

        if not self._check_integrity():
            raise RuntimeError('Dataset not found or corrupted.' +
                               ' You can use download=True to download it')

        if self.train:
            downloaded_list = self.train_list
        if self.valid:
            downloaded_list = self.valid_list
        if self.test:
            downloaded_list = self.test_list

        self.data = []
        self.targets = []

        for file_name, checksum in downloaded_list:
            file_path = os.path.join(self.root, self.base_folder, file_name)
            with open(file_path, 'rb') as f:
                entry = pickle.load(f, encoding='latin1')
                self.data.append(entry['data'])
                if 'labels' in entry:
                    self.targets.extend(entry['labels'])
                else:
                    self.targets.extend(entry['fine_labels'])

        self.data = np.vstack(self.data).reshape(-1, 3, 32, 32)
        self.data = self.data.transpose((0, 2, 3, 1))
        if noisy == True:
            if self.valid:
                t_ = self._load_noise_label(True)[40000:]
                print(f"val data size_{len(self.data)}")
                self.data = self.data
            elif self.train:
                t_ = self._load_noise_label(True)[:40000]
                self.data = self.data
            else:
                t_ = self._load_noise_label(False)
            self.targets = t_.tolist()

        self._load_meta()

    def _load_noise_label(self, is_train):
        '''
        I adopte .pt rather .pth according to this discussion:
        https://github.com/pytorch/pytorch/issues/14864
        '''
        dataset_path = "./datasets/CIFAR-N"
        key_clean = 'clean_label'
        key_worst = 'worse_label'
        key_aggre = 'aggre_label'
        key_random1 = 'random_label1'
        key_random2 = 'random_label2'
        key_random3 = 'random_label3'
        if opt1 == 1:
            fname = "CIFAR-10_human.pt"
        elif opt1 == 2:
            fname = "CIFAR-100_human.pt"
        if opt2 == 1:
            key = key_clean
        elif opt2 == 2:
            key = key_worst
        elif opt2 == 3:
            key =key_aggre
        elif opt2 == 4:
            key = key_random1
        elif opt2 == 5:
            key = key_random2
        elif opt2 == 6:
            key = key_random3

        fpath = os.path.join(dataset_path, fname)
        noise_label_torch = torch.load(fpath)
        noise_label_torch = noise_label_torch[key]
        return noise_label_torch

    def _load_meta(self):
        path = os.path.join(self.root, self.base_folder, self.meta['filename'])
        if not check_integrity(path, self.meta['md5']):
            raise RuntimeError('Dataset metadata file not found or corrupted.' +
                               ' You can use download=True to download it')
        with open(path, 'rb') as infile:
            data = pickle.load(infile, encoding='latin1')
            self.classes = data[self.meta['key']]
        self.class_to_idx = {_class: i for i, _class in enumerate(self.classes)}

    def __getitem__(self, index):

        img, target = self.data[index], self.targets[index]
        img = Image.fromarray(img)  # 将array转为image

        if self.transform is not None:
            img = self.transform(img)

        if self.target_transform is not None:
            target = self.target_transform(target)

        idx = index

        return idx, img, target

    def __len__(self):
        return len(self.data)

    def _check_integrity(self):
        root = self.root
        for fentry in (self.train_list + self.test_list):
            filename, md5 = fentry[0], fentry[1]
            fpath = os.path.join(root, self.base_folder, filename)
            if not check_integrity(fpath, md5):
                return False
        return True

    def download(self):
        import tarfile

        if self._check_integrity():
            print('Files already downloaded and verified')
            return

        download_url(self.url, self.root, self.filename, self.tgz_md5)

        with tarfile.open(os.path.join(self.root, self.filename), "r:gz") as tar:
            tar.extractall(path=self.root)

    def __repr__(self):
        fmt_str = 'Dataset ' + self.__class__.__name__ + '\n'
        fmt_str += '    Number of datapoints: {}\n'.format(self.__len__())
        tmp = 'train' if self.train is True else 'test'
        fmt_str += '    Split: {}\n'.format(tmp)
        fmt_str += '    Root Location: {}\n'.format(self.root)
        tmp = '    Transforms (if any): '
        fmt_str += '{0}{1}\n'.format(tmp, self.transform.__repr__().replace('\n', '\n' + ' ' * len(tmp)))
        tmp = '    Target Transforms (if any): '
        fmt_str += '{0}{1}'.format(tmp, self.target_transform.__repr__().replace('\n', '\n' + ' ' * len(tmp)))
        return fmt_str


normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225])


def peer_data_train(batch_size, img_size=(32, 32)):
    peer_dataset = CIFAR10_(root=root, train=True, valid=False, test=False, noisy=True, transform=transforms.Compose([
        transforms.RandomCrop(32, 4),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(15),
        transforms.ToTensor(),
        normalize,
    ]))

    peer_dataloader = torch.utils.data.DataLoader(
        peer_dataset,
        batch_size=batch_size,
        shuffle=True,
        drop_last=True)

    return peer_dataloader


def peer_data_val(batch_size, img_size=(32, 32)):
    peer_dataset = CIFAR10_(root=root, train=False, valid=True, test=False, noisy=True, transform=transforms.Compose([
        transforms.ToTensor(),
        normalize,
    ]))

    peer_dataloader = torch.utils.data.DataLoader(
        peer_dataset,
        batch_size=batch_size,
        shuffle=True,
        drop_last=True)

    return peer_dataloader


train_dataset_noisy = CIFAR10_(root=root, train=True, valid=False, test=False, noisy=True,
                               transform=transforms.Compose([
                                   transforms.RandomCrop(32, 4),
                                   transforms.RandomHorizontalFlip(),
                                   transforms.RandomRotation(15),
                                   transforms.ToTensor(),
                                   normalize,
                               ]))

train_loader_noisy = torch.utils.data.DataLoader(dataset=train_dataset_noisy, batch_size=batch_size, shuffle=True,
                                                 num_workers=0)

train_loader_noisy_unshuffle = torch.utils.data.DataLoader(dataset=train_dataset_noisy, batch_size=batch_size,
                                                           shuffle=False)

valid_dataset_noisy = CIFAR10_(root=root, train=False, valid=True, test=False, noisy=True,
                               transform=transforms.Compose([
                                   transforms.ToTensor(),
                                   normalize,
                               ]))

valid_dataset_clean = CIFAR10_(root=root, train=False, valid=True, test=False, noisy=False,
                               transform=transforms.Compose([
                                   transforms.ToTensor(),
                                   normalize, ]))

valid_loader_noisy = torch.utils.data.DataLoader(dataset=valid_dataset_noisy, batch_size=batch_size, shuffle=False,
                                                 num_workers=0)

valid_loader_clean = torch.utils.data.DataLoader(dataset=valid_dataset_clean, batch_size=batch_size, shuffle=False,
                                                 num_workers=0)

test_dataset = CIFAR10_(root=root, train=False, valid=False, test=True, noisy=False, transform=transforms.Compose([
    transforms.ToTensor(),
    normalize,
]))
test_loader_ = torch.utils.data.DataLoader(dataset=test_dataset, batch_size=batch_size, shuffle=False, num_workers=0)