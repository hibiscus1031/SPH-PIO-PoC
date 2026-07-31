# Hardware and software audit

Audit date: 2026-07-31. Command outputs are recorded below with host name,
serial/UUID/UDID, and personally identifying volume/application labels redacted.
No account, credential, or network information was collected.

## `sw_vers`

```text
ProductName:    macOS
ProductVersion: 26.5.2
BuildVersion:   25F84
```

## `uname -a`

```text
Darwin [REDACTED_HOSTNAME] 25.5.0 Darwin Kernel Version 25.5.0: Tue Jun 9 22:27:52 PDT 2026; root:xnu-12377.121.10~1/RELEASE_ARM64_T8112 arm64
```

## `uname -m`

```text
arm64
```

## `system_profiler SPHardwareDataType`

```text
Hardware:

    Hardware Overview:

      Model Name: MacBook Air
      Model Identifier: Mac14,2
      Model Number: Z15W0003HCH/A
      Chip: Apple M2
      Total Number of Cores: 8 (4 Performance and 4 Efficiency)
      Memory: 16 GB
      System Firmware Version: 18000.121.3
      OS Loader Version: 18000.121.3
      Serial Number (system): [REDACTED]
      Hardware UUID: [REDACTED]
      Provisioning UDID: [REDACTED]
      Activation Lock Status: Disabled
```

## `system_profiler SPDisplaysDataType`

```text
Graphics/Displays:

    Apple M2:

      Chipset Model: Apple M2
      Type: GPU
      Bus: Built-In
      Total Number of Cores: 8
      Vendor: Apple (0x106b)
      Metal Support: Metal 4
      Displays:
        Color LCD:
          Display Type: Built-in Liquid Retina Display
          Resolution: 2560 x 1664 Retina
          Main Display: Yes
          Mirror: Off
          Online: Yes
          Automatically Adjust Brightness: No
          Connection Type: Internal
```

## `df -h`

```text
Filesystem                                Size    Used   Avail Capacity iused ifree %iused  Mounted on
/dev/disk3s1s1                           460Gi    12Gi   226Gi     5%    459k  2.4G    0%   /
devfs                                    201Ki   201Ki     0Bi   100%     696     0  100%   /dev
/dev/disk3s6                             460Gi   1.0Gi   226Gi     1%       1  2.4G    0%   /System/Volumes/VM
/dev/disk3s2                             460Gi   8.4Gi   226Gi     4%    1.5k  2.4G    0%   /System/Volumes/Preboot
/dev/disk3s4                             460Gi   5.6Mi   226Gi     1%     112  2.4G    0%   /System/Volumes/Update
/dev/disk1s2                             500Mi   6.0Mi   482Mi     2%       1  4.9M  0%   /System/Volumes/xarts
/dev/disk1s1                             500Mi   5.8Mi   482Mi     1%      31  4.9M  0%   /System/Volumes/iSCPreboot
/dev/disk1s3                             500Mi   1.3Mi   482Mi     1%      65  4.9M  0%   /System/Volumes/Hardware
/dev/disk3s5                             460Gi   212Gi   226Gi    49%    2.1M  2.4G  0%   /System/Volumes/Data
[REDACTED_APP_MOUNT]                     460Gi   209Gi   230Gi    48%    2.1M  2.4G  0%   [REDACTED_TEMPORARY_MOUNT]
/dev/disk4s1                             931Gi    35Gi   897Gi     4%       1     0 100%   /Volumes/[REDACTED_VOLUME_LABEL]
```

## Toolchain commands

```text
$ xcode-select -p
/Library/Developer/CommandLineTools

$ which python3
/opt/miniconda3/bin/python3

$ python3 --version
Python 3.13.9

$ which conda
/opt/miniconda3/bin/conda

$ which brew
/opt/homebrew/bin/brew

$ git --version
git version 2.50.1 (Apple Git-155)
```

## Isolated project environment

Created without modifying system Python:

```text
conda create -y -n sph-pio-poc python=3.12 pip
```

The resulting environment is `/opt/miniconda3/envs/sph-pio-poc`, Python 3.12.13.
Installed project packages: `torch 2.13.0`, `numpy 2.5.1`, `scipy 1.18.0`,
`matplotlib 3.11.1`, `h5py 3.16.0`, `pytest 9.1.1`, `pyyaml 6.0.3`,
`tqdm 4.70.0`, and `pandas 3.0.5`. The installed torch wheel reported
`macosx_14_0_arm64`; no CUDA, cuDNN, or NVIDIA package was requested or installed.
