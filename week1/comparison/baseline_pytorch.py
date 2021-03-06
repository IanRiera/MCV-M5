import torch
import torchvision
import torchvision.transforms as transforms
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.utils.tensorboard import SummaryWriter

from utils import *

results_dir = '../results/baseline_'
log_dir = '../log/'
model_dir = '../models/'

train_data_dir = '/home/mcv/datasets/MIT_split/train'
test_data_dir = '/home/mcv/datasets/MIT_split/test'

img_size = 256
batch_size = 16
number_of_epoch = 100

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

# ---- LOADING DATASET--------
transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Resize((img_size, img_size)),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

train_set = torchvision.datasets.ImageFolder(train_data_dir, transform=transform)
train_loader = torch.utils.data.DataLoader(train_set, batch_size=batch_size,
                                           num_workers=4, shuffle=True)

test_set = torchvision.datasets.ImageFolder(test_data_dir, transform=transform)
test_loader = torch.utils.data.DataLoader(test_set, batch_size=batch_size,
                                          num_workers=4, shuffle=False)

# ---- DEFINING MODEL--------
class Baseline(nn.Module):
    def __init__(self):
        super(Baseline, self).__init__()
        self.conv1 = nn.Conv2d(3, 64, 3)
        self.conv2 = nn.Conv2d(64, 32, 3)
        self.pool = nn.MaxPool2d(2, 2)
        self.fc1 = nn.Linear(32 * 62 * 62, 8)

    def forward(self, x):
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = x.view(-1, self.num_flat_features(x))
        x = F.softmax(self.fc1(x))
        x = torch.squeeze(x)
        return x

    def num_flat_features(self, x):
        size = x.size()[1:]  # all dimensions except the batch dimension
        num_features = 1
        for s in size:
            num_features *= s
        return num_features

model = Baseline()

def weights_init(m):
    if isinstance(m, nn.Conv2d):
        nn.init.xavier_normal_(m.weight)

model.apply(weights_init)
model.to(device)
print(model)
total_params = sum(p.numel() for p in model.parameters())
print('Number of parameters for this model: {}'.format(total_params))

images, _ = next(iter(train_loader))
writer = SummaryWriter(f'tb/baseline/')
writer.add_graph(model, images.to(device))
writer.close()

criterion = nn.CrossEntropyLoss()
optimizer = optim.SGD(model.parameters(), lr=0.01, momentum=0.9)

writer_train = SummaryWriter(f'tb/baseline/train')
writer_test = SummaryWriter(f'tb/baseline/test')

train_acc_hist = []
test_acc_hist = []
train_loss_hist = []
test_loss_hist = []

for epoch in range(number_of_epoch):
    model.train()

    # training statistics
    losses, acc, count = [], [], []
    for batch_idx, (inputs, labels) in enumerate(train_loader):
        # transfer data to GPU
        inputs, labels = inputs.to(device), labels.to(device)

        optimizer.zero_grad()

        outputs = model(inputs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        # calculating this way to account for the fact that the
        # last batch may have different batch size
        batch_size = inputs.shape[0]
        # get number of right predictions
        correct_predictions = (outputs.argmax(dim=1) == labels).float().sum()
        # add to list
        losses.append(batch_size * loss.item()), count.append(batch_size), acc.append(correct_predictions)

        writer_train.add_scalar('per_batch/train_loss', loss.item(), epoch * len(train_loader) + batch_idx)

    # accumulate/average statistics
    n = sum(count)
    train_loss_epoch = sum(losses) / n
    train_acc_epoch = sum(acc) / n

    train_loss_hist.append(train_loss_epoch)
    train_acc_hist.append(train_acc_epoch)

    writer_train.add_scalar('per_epoch/losses', train_loss_epoch, epoch)
    writer_train.add_scalar('per_epoch/accuracy', train_acc_epoch, epoch)

    # validation
    model.eval()

    with torch.no_grad():
        losses, acc, count = [], [], []
        for batch_idx, (inputs, labels) in enumerate((test_loader)):
            # transfer data to GPU
            inputs, labels = inputs.to(device), labels.to(device)
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            batch_size = inputs.shape[0]
            # get number of right predictions
            correct_predictions = (outputs.argmax(dim=1) == labels).float().sum()
            # add to list
            losses.append(batch_size * loss.item()), count.append(batch_size), acc.append(correct_predictions)

            writer_test.add_scalar('per_batch/test_loss', loss.item(), epoch * len(test_loader) + batch_idx)

    # accumulate/average statistics
    n = sum(count)
    test_loss_epoch = sum(losses) / n
    test_acc_epoch = sum(acc) / n

    test_loss_hist.append(test_loss_epoch)
    test_acc_hist.append(test_acc_epoch)

    writer_test.add_scalar('per_epoch/losses', test_loss_epoch, epoch)
    writer_test.add_scalar('per_epoch/accuracy', test_acc_epoch, epoch)

    print(f"Epoch{epoch}, train_accuracy:{train_acc_epoch:.4f}, test_accuracy:{test_acc_epoch:.4f}, train_loss:{train_loss_epoch:.4f}, test_loss:{test_loss_epoch:.4f}")

# Save model
torch.save(model.state_dict(), model_dir + '/baseline_oscar_weights.pkl')

plot_accuracy(train_acc_hist, test_acc_hist, results_dir, xmax=number_of_epoch)
plot_loss(train_loss_hist, test_loss_hist, results_dir, xmax=number_of_epoch)
