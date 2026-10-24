import pytest
from unittest.mock import patch

from frame_allocator import FrameAllocator
from page_table import PageTable
from physical_memory import PhysicalMemory
from tlb import TLB
from virtual_memory import VirtualMemory


# ---------- PhysicalMemory ----------

def test_physical_memory_invalid_size():
    with pytest.raises(ValueError):
        PhysicalMemory(0)


def test_physical_memory_starts_zeroed():
    assert PhysicalMemory(8).read_bytes(0, 8) == bytes(8)


def test_physical_memory_roundtrip_and_type():
    pm = PhysicalMemory(8)
    pm.write_bytes(2, b"\x01\x02\x03")
    result = pm.read_bytes(2, 3)
    assert result == b"\x01\x02\x03"
    assert type(result) is bytes


def test_physical_memory_exact_end_is_valid():
    pm = PhysicalMemory(8)
    pm.write_bytes(6, b"\xaa\xbb")
    assert pm.read_bytes(6, 2) == b"\xaa\xbb"


@pytest.mark.parametrize("address, length", [(-1, 1), (7, 2), (8, 1), (0, -1)])
def test_physical_memory_read_out_of_range(address, length):
    with pytest.raises(ValueError):
        PhysicalMemory(8).read_bytes(address, length)


def test_physical_memory_write_out_of_range_writes_nothing():
    pm = PhysicalMemory(8)
    with pytest.raises(ValueError):
        pm.write_bytes(6, b"\x01\x02\x03")
    assert pm.read_bytes(0, 8) == bytes(8)


# ---------- FrameAllocator ----------

def test_allocator_invalid_size():
    with pytest.raises(ValueError):
        FrameAllocator(0)


def test_allocator_hands_out_frames_in_order_then_none():
    allocator = FrameAllocator(3)
    assert [allocator.allocate() for _ in range(3)] == [0, 1, 2]
    assert allocator.allocate() is None


# ---------- PageTable ----------

def test_page_table_invalid_size():
    with pytest.raises(ValueError):
        PageTable(0)


def test_page_table_unmapped_is_none():
    assert PageTable(4).look_up(2) is None


def test_page_table_map_and_look_up():
    pt = PageTable(4)
    pt.map(2, 7)
    assert pt.look_up(2) == 7


def test_page_table_frame_zero_is_a_valid_mapping():
    pt = PageTable(4)
    pt.map(1, 0)
    assert pt.look_up(1) == 0


@pytest.mark.parametrize("page", [-1, 4])
def test_page_table_look_up_out_of_range_is_none(page):
    assert PageTable(4).look_up(page) is None


@pytest.mark.parametrize("page", [-1, 4])
def test_page_table_map_out_of_range(page):
    with pytest.raises(IndexError):
        PageTable(4).map(page, 0)


# ---------- TLB ----------

def test_tlb_invalid_size():
    with pytest.raises(ValueError):
        TLB(0)


def test_tlb_miss_then_hit():
    tlb = TLB(2)
    assert tlb.look_up(1) is None
    tlb.insert(1, 5)
    assert tlb.look_up(1) == 5


def test_tlb_evicts_least_recently_used():
    tlb = TLB(2)
    tlb.insert(1, 10)
    tlb.insert(2, 20)
    tlb.look_up(1)          # page 2 is now the least recently used
    tlb.insert(3, 30)
    assert tlb.look_up(2) is None
    assert tlb.look_up(1) == 10
    assert tlb.look_up(3) == 30


def test_tlb_reinserting_existing_page_does_not_evict():
    tlb = TLB(2)
    tlb.insert(1, 10)
    tlb.insert(2, 20)
    tlb.insert(1, 11)
    assert tlb.look_up(1) == 11
    assert tlb.look_up(2) == 20


# ---------- VirtualMemory ----------

@pytest.fixture
def vm():
    return VirtualMemory(page_size=4, num_pages=8, num_frames=4, tlb_size=2)


@pytest.mark.parametrize("args", [(0, 8, 4, 2), (4, 0, 4, 2), (4, 8, 0, 2), (4, 8, 4, 0)])
def test_vm_invalid_parameters(args):
    with pytest.raises(ValueError):
        VirtualMemory(*args)


def test_vm_unwritten_memory_reads_zero(vm):
    assert vm.read_bytes(5, 3) == bytes(3)


def test_vm_single_byte_roundtrip(vm):
    vm.write_bytes(9, b"\x7f")
    assert vm.read_bytes(9, 1) == b"\x7f"


def test_vm_zero_length_touches_nothing(vm):
    assert vm.read_bytes(0, 0) == b""
    vm.write_bytes(0, b"")
    assert vm.page_table.look_up(0) is None


def test_vm_exact_page_fill_uses_one_page(vm):
    vm.write_bytes(4, b"abcd")
    assert vm.read_bytes(4, 4) == b"abcd"
    assert vm.page_table.look_up(1) is not None
    assert vm.page_table.look_up(0) is None
    assert vm.page_table.look_up(2) is None


def test_vm_straddle_by_one_byte(vm):
    vm.write_bytes(3, b"ab")
    assert vm.read_bytes(3, 2) == b"ab"
    assert vm.read_bytes(3, 1) == b"a"
    assert vm.read_bytes(4, 1) == b"b"


def test_vm_straddle_across_non_adjacent_frames(vm):
    vm.read_bytes(4, 1)    # page 1 gets frame 0
    vm.read_bytes(20, 1)   # page 5 gets frame 1
    vm.read_bytes(0, 1)    # page 0 gets frame 2
    frame_0 = vm.page_table.look_up(0)
    frame_1 = vm.page_table.look_up(1)
    assert frame_1 != frame_0 + 1

    vm.write_bytes(2, b"WXYZ")
    assert vm.read_bytes(2, 4) == b"WXYZ"


def test_vm_multi_page_write_and_read(vm):
    data = bytes(range(1, 14))
    vm.write_bytes(1, data)
    assert vm.read_bytes(1, len(data)) == data


def test_vm_last_valid_address(vm):
    vm.write_bytes(31, b"\x09")
    assert vm.read_bytes(31, 1) == b"\x09"
    vm.write_bytes(28, b"abcd")
    assert vm.read_bytes(28, 4) == b"abcd"


@pytest.mark.parametrize("address, length", [(32, 1), (31, 2), (-1, 1), (0, -1), (0, 33)])
def test_vm_read_out_of_range_raises_value_error(vm, address, length):
    with pytest.raises(ValueError):
        vm.read_bytes(address, length)


@pytest.mark.parametrize("address, length", [(32, 1), (31, 2), (-1, 1), (0, 33)])
def test_vm_write_out_of_range_raises_value_error(vm, address, length):
    with pytest.raises(ValueError):
        vm.write_bytes(address, bytes(length))


def test_vm_invalid_write_changes_nothing(vm):
    with pytest.raises(ValueError):
        vm.write_bytes(30, b"abcd")
    assert vm.page_table.look_up(7) is None
    assert vm.read_bytes(28, 4) == bytes(4)


def test_vm_translates_once_per_page_touched(vm):
    with patch.object(vm.tlb, "look_up", wraps=vm.tlb.look_up) as spy:
        vm.read_bytes(0, 4)
        assert spy.call_count == 1
        spy.reset_mock()
        vm.read_bytes(3, 2)
        assert spy.call_count == 2


def test_vm_tlb_hit_skips_page_table(vm):
    vm.read_bytes(0, 1)
    with patch.object(vm.page_table, "look_up", wraps=vm.page_table.look_up) as spy:
        vm.read_bytes(1, 1)
        assert spy.call_count == 0


def test_vm_tlb_miss_with_mapped_page_does_not_allocate_again():
    vm = VirtualMemory(page_size=4, num_pages=8, num_frames=4, tlb_size=1)
    vm.write_bytes(0, b"A")       # page 0 gets a frame
    vm.write_bytes(4, b"B")       # page 1 pushes page 0 out of the TLB
    frame = vm.page_table.look_up(0)
    assert vm.read_bytes(0, 1) == b"A"
    assert vm.page_table.look_up(0) == frame


def test_vm_raises_memory_error_when_frames_run_out():
    vm = VirtualMemory(page_size=4, num_pages=4, num_frames=2, tlb_size=2)
    vm.read_bytes(0, 1)
    vm.read_bytes(4, 1)
    with pytest.raises(MemoryError):
        vm.read_bytes(8, 1)
    # already mapped pages keep working
    assert vm.read_bytes(0, 1) == b"\x00"


def test_vm_partial_write_is_currently_allowed():
    # Pins current behavior. Flip this if writes should be all-or-nothing.
    vm = VirtualMemory(page_size=4, num_pages=2, num_frames=1, tlb_size=1)
    with pytest.raises(MemoryError):
        vm.write_bytes(0, b"abcdef")
    assert vm.read_bytes(0, 4) == b"abcd"