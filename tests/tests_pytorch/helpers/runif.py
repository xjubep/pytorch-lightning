# Copyright The PyTorch Lightning team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import sys
from typing import Optional

import pytest
import torch
from packaging.version import Version
from pkg_resources import get_distribution

from pytorch_lightning.accelerators.mps import _MPS_AVAILABLE
from pytorch_lightning.callbacks.progress.rich_progress import _RICH_AVAILABLE
from pytorch_lightning.overrides.fairscale import _FAIRSCALE_AVAILABLE
from pytorch_lightning.strategies.bagua import _BAGUA_AVAILABLE
from pytorch_lightning.strategies.deepspeed import _DEEPSPEED_AVAILABLE
from pytorch_lightning.utilities.imports import (
    _APEX_AVAILABLE,
    _FAIRSCALE_FULLY_SHARDED_AVAILABLE,
    _HIVEMIND_AVAILABLE,
    _HOROVOD_AVAILABLE,
    _HPU_AVAILABLE,
    _IPU_AVAILABLE,
    _OMEGACONF_AVAILABLE,
    _PSUTIL_AVAILABLE,
    _TORCH_GREATER_EQUAL_1_10,
    _TORCH_QUANTIZE_AVAILABLE,
    _TPU_AVAILABLE,
)

_HOROVOD_NCCL_AVAILABLE = False
if _HOROVOD_AVAILABLE:
    import horovod

    try:

        # `nccl_built` returns an integer
        _HOROVOD_NCCL_AVAILABLE = bool(horovod.torch.nccl_built())
    except AttributeError:
        # AttributeError can be raised if MPI is not available:
        # https://github.com/horovod/horovod/blob/v0.23.0/horovod/torch/__init__.py#L33-L34
        pass


class RunIf:
    """RunIf wrapper for simple marking specific cases, fully compatible with pytest.mark::

    @RunIf(min_torch="0.0")
    @pytest.mark.parametrize("arg1", [1, 2.0])
    def test_wrapper(arg1):
        assert arg1 > 0.0
    """

    def __new__(
        self,
        *args,
        min_cuda_gpus: int = 0,
        min_torch: Optional[str] = None,
        max_torch: Optional[str] = None,
        min_python: Optional[str] = None,
        quantization: bool = False,
        amp_apex: bool = False,
        bf16_cuda: bool = False,
        tpu: bool = False,
        ipu: bool = False,
        hpu: bool = False,
        mps: Optional[bool] = None,
        horovod: bool = False,
        horovod_nccl: bool = False,
        skip_windows: bool = False,
        standalone: bool = False,
        fairscale: bool = False,
        fairscale_fully_sharded: bool = False,
        deepspeed: bool = False,
        rich: bool = False,
        omegaconf: bool = False,
        slow: bool = False,
        bagua: bool = False,
        psutil: bool = False,
        hivemind: bool = False,
        **kwargs,
    ):
        """
        Args:
            *args: Any :class:`pytest.mark.skipif` arguments.
            min_cuda_gpus: Require this number of gpus.
            min_torch: Require that PyTorch is greater or equal than this version.
            max_torch: Require that PyTorch is less than this version.
            min_python: Require that Python is greater or equal than this version.
            quantization: Require that `torch.quantization` is available.
            amp_apex: Require that NVIDIA/apex is installed.
            bf16_cuda: Require that CUDA device supports bf16.
            tpu: Require that TPU is available.
            ipu: Require that IPU is available.
            hpu: Require that HPU is available.
            mps: If True: Require that MPS (Apple Silicon) is available,
                if False: Explicitly Require that MPS is not available
            horovod: Require that Horovod is installed.
            horovod_nccl: Require that Horovod is installed with NCCL support.
            skip_windows: Skip for Windows platform.
            standalone: Mark the test as standalone, our CI will run it in a separate process.
            fairscale: Require that facebookresearch/fairscale is installed.
            fairscale_fully_sharded: Require that `fairscale` fully sharded support is available.
            deepspeed: Require that microsoft/DeepSpeed is installed.
            rich: Require that willmcgugan/rich is installed.
            omegaconf: Require that omry/omegaconf is installed.
            slow: Mark the test as slow, our CI will run it in a separate job.
            bagua: Require that BaguaSys/bagua is installed.
            psutil: Require that psutil is installed.
            hivemind: Require that Hivemind is installed.
            **kwargs: Any :class:`pytest.mark.skipif` keyword arguments.
        """
        conditions = []
        reasons = []

        if min_cuda_gpus:
            conditions.append(torch.cuda.device_count() < min_cuda_gpus)
            reasons.append(f"GPUs>={min_cuda_gpus}")

        if min_torch:
            torch_version = get_distribution("torch").version
            conditions.append(Version(torch_version) < Version(min_torch))
            reasons.append(f"torch>={min_torch}")

        if max_torch:
            torch_version = get_distribution("torch").version
            conditions.append(Version(torch_version) >= Version(max_torch))
            reasons.append(f"torch<{max_torch}")

        if min_python:
            py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            conditions.append(Version(py_version) < Version(min_python))
            reasons.append(f"python>={min_python}")

        if quantization:
            _miss_default = "fbgemm" not in torch.backends.quantized.supported_engines
            conditions.append(not _TORCH_QUANTIZE_AVAILABLE or _miss_default)
            reasons.append("PyTorch quantization")

        if amp_apex:
            conditions.append(not _APEX_AVAILABLE)
            reasons.append("NVIDIA Apex")

        if bf16_cuda:
            try:
                cond = not (torch.cuda.is_available() and _TORCH_GREATER_EQUAL_1_10 and torch.cuda.is_bf16_supported())
            except (AssertionError, RuntimeError) as e:
                # AssertionError: Torch not compiled with CUDA enabled
                # RuntimeError: Found no NVIDIA driver on your system.
                is_unrelated = "Found no NVIDIA driver" not in str(e) or "Torch not compiled with CUDA" not in str(e)
                if is_unrelated:
                    raise e
                cond = True

            conditions.append(cond)
            reasons.append("CUDA device bf16")

        if skip_windows:
            conditions.append(sys.platform == "win32")
            reasons.append("unimplemented on Windows")

        if tpu:
            conditions.append(not _TPU_AVAILABLE)
            reasons.append("TPU")

        if ipu:
            env_flag = os.getenv("PL_RUN_IPU_TESTS", "0")
            conditions.append(env_flag != "1" or not _IPU_AVAILABLE)
            reasons.append("IPU")
            kwargs["ipu"] = True

        if hpu:
            conditions.append(not _HPU_AVAILABLE)
            reasons.append("HPU")

        if mps is not None:
            if mps:
                conditions.append(not _MPS_AVAILABLE)
                reasons.append("MPS")
            else:
                conditions.append(_MPS_AVAILABLE)
                reasons.append("not MPS")

        if horovod:
            conditions.append(not _HOROVOD_AVAILABLE)
            reasons.append("Horovod")

        if horovod_nccl:
            conditions.append(not _HOROVOD_NCCL_AVAILABLE)
            reasons.append("Horovod with NCCL")

        if standalone:
            env_flag = os.getenv("PL_RUN_STANDALONE_TESTS", "0")
            conditions.append(env_flag != "1")
            reasons.append("Standalone execution")
            # used in tests/conftest.py::pytest_collection_modifyitems
            kwargs["standalone"] = True

        if fairscale:
            conditions.append(not _FAIRSCALE_AVAILABLE)
            reasons.append("Fairscale")

        if fairscale_fully_sharded:
            conditions.append(not _FAIRSCALE_FULLY_SHARDED_AVAILABLE)
            reasons.append("Fairscale Fully Sharded")

        if deepspeed:
            conditions.append(not _DEEPSPEED_AVAILABLE)
            reasons.append("Deepspeed")

        if rich:
            conditions.append(not _RICH_AVAILABLE)
            reasons.append("Rich")

        if omegaconf:
            conditions.append(not _OMEGACONF_AVAILABLE)
            reasons.append("omegaconf")

        if slow:
            env_flag = os.getenv("PL_RUN_SLOW_TESTS", "0")
            conditions.append(env_flag != "1")
            reasons.append("Slow test")
            # used in tests/conftest.py::pytest_collection_modifyitems
            kwargs["slow"] = True

        if bagua:
            conditions.append(not _BAGUA_AVAILABLE or sys.platform in ("win32", "darwin"))
            reasons.append("Bagua")

        if psutil:
            conditions.append(not _PSUTIL_AVAILABLE)
            reasons.append("psutil")

        if hivemind:
            conditions.append(not _HIVEMIND_AVAILABLE or sys.platform in ("win32", "darwin"))
            reasons.append("Hivemind")

        reasons = [rs for cond, rs in zip(conditions, reasons) if cond]
        return pytest.mark.skipif(
            *args, condition=any(conditions), reason=f"Requires: [{' + '.join(reasons)}]", **kwargs
        )


@RunIf(min_torch="99")
def test_always_skip():
    exit(1)


@pytest.mark.parametrize("arg1", [0.5, 1.0, 2.0])
@RunIf(min_torch="0.0")
def test_wrapper(arg1: float):
    assert arg1 > 0.0
