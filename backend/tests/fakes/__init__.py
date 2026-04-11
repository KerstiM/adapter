"""In-memory fake implementations of ports for unit testing.

``FixedClock`` is re-exported from the canonical ``adapters.testing``
location so tests and production wiring share a single implementation.
"""

from adapters.testing.clock_fixed import FixedClock
from tests.fakes.fake_dataset_port import FakeDatasetPort
from tests.fakes.fake_output_port import FakeOutputPort
from tests.fakes.fake_spec_port import FakeSpecPort

__all__ = [
    "FakeDatasetPort",
    "FakeOutputPort",
    "FakeSpecPort",
    "FixedClock",
]
