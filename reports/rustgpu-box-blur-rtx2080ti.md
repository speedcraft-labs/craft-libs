### lightcraft box blur r=128 on AdapterInfo { name: "NVIDIA GeForce RTX 2080 Ti", vendor: 4318, device: 7687, device_type: DiscreteGpu, device_pci_bus_id: "0000:01:00.0", driver: "NVIDIA", driver_info: "550.163.01", backend: Vulkan, subgroup_min_size: 32, subgroup_max_size: 32, transient_saves_memory: Some(false), limit_bucket: None }

Publishable.

linux x86_64 (Linux 6.12.115+deb13.1-cloud-amd64), AMD Ryzen 9 5900XT 16-Core Processor, 6 logical cores, 86.4 GiB, release opt-level 3, 2026-11-08T08:23:50+00:00.
Revs old `80a4d6d3baeb05dd0d446f001b3ac9b7188f612a` new `38352190932e8d0cd8048d0818f1c2c0ee90defc`. Load before 0.27 after 0.21 (limit 3.00). 10 runs per side, 2000 resamples, seed 12648430.

| input | old median | old MAD | new median | new MAD | new/old (95% CI) | verdict |
|---|---:|---:|---:|---:|---:|---|
| pngsuite/basn6a08.png | 177.101 us | 30.343 us | 173.057 us | 26.314 us | 0.977 [0.745, 1.225] | inconclusive (CI includes 1.0) |
| pngsuite/basn2c16.png | 170.428 us | 31.951 us | 179.199 us | 34.780 us | 1.051 [0.615, 1.769] | inconclusive (CI includes 1.0) |
| pngsuite/basn0g08.png | 158.054 us | 12.414 us | 156.716 us | 1.813 us | 0.992 [0.830, 1.204] | inconclusive (CI includes 1.0) |
| pngsuite/basn4a08.png | 171.936 us | 19.477 us | 161.401 us | 9.558 us | 0.939 [0.812, 1.552] | inconclusive (CI includes 1.0) |
| synthetic-24mp-r128 | 13.666 ms | 102.694 us | 12.341 ms | 45.386 us | 0.903 [0.653, 1.248] | inconclusive (CI includes 1.0) |
| **geomean of 5** | | | | | 0.971 [0.855, 1.154] | inconclusive (CI includes 1.0) |

Process CPU time, geomean new/old: 0.971 [0.853, 1.107] (inconclusive (CI includes 1.0)).
