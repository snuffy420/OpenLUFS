"""Bounded track workers with serialized progress and cooperative cancellation."""
from concurrent.futures import ThreadPoolExecutor
import ctypes
import os
from queue import Queue,Empty


def available_memory():
    try:
        if os.name=='nt':
            class MemoryStatus(ctypes.Structure):
                _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(name,ctypes.c_ulonglong) for name in
                    ['total','available','total_page','available_page','total_virtual','available_virtual','extended']]
            status=MemoryStatus();status.length=ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):return status.available
        else:
            return os.sysconf('SC_AVPHYS_PAGES')*os.sysconf('SC_PAGE_SIZE')
    except (AttributeError,OSError,ValueError):pass
    return None


def worker_count(count,requested=None):
    if requested is not None and (isinstance(requested,bool) or not isinstance(requested,int) or not 1<=requested<=32):
        raise ValueError('Workers must be an integer between 1 and 32.')
    cpus=os.cpu_count() or 1
    desired=requested if requested is not None else min(4,max(1,cpus//2))
    cpu_limit=max(1,cpus-1)
    available=available_memory()
    memory_limit=max(1,(available-512*1024**2)//(512*1024**2)) if available is not None else 4
    return max(1,min(max(1,count),desired,cpu_limit,memory_limit))


def run_tracks(items,job,cancel,callback=None,workers=None):
    """Return terminal outcomes in source order; callbacks run on the caller thread.

    Submit at most the worker count at once. Cancellation stops submission, signals
    running jobs via their shared event, and waits for their subprocess/temp cleanup.
    """
    items=list(items);callback=callback or (lambda *args:None)
    count=worker_count(len(items),workers)
    if not items or cancel.is_set():return []
    events=Queue();outcomes={};pending={};next_index=0

    def work(index,item):
        from .engine import Cancelled
        try:
            if cancel.is_set():raise Cancelled()
            stage,payload=job(index,item,lambda stage,payload=None:events.put((index,False,stage,payload)))
        except Cancelled:stage,payload='Cancelled',None
        except Exception as error:stage,payload='Failed',str(error)
        events.put((index,True,stage,payload))

    with ThreadPoolExecutor(max_workers=count,thread_name_prefix='OpenLUFS-track') as pool:
        try:
            def fill():
                nonlocal next_index
                while not cancel.is_set() and next_index<len(items) and len(pending)<count:
                    index=next_index;next_index+=1
                    pending[index]=pool.submit(work,index,items[index])
            fill()
            while pending:
                try:index,terminal,stage,payload=events.get(timeout=.1)
                except Empty:continue
                callback(index,stage,payload)
                if terminal:
                    outcomes[index]=(stage,payload);pending.pop(index);fill()
        except BaseException:
            cancel.set()
            raise
    return [(index,*outcomes[index]) for index in sorted(outcomes)]
