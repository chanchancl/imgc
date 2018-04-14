# -*- coding:utf-8 -*-

import os
import sys
from PIL import Image
import threading
import time
import logging

# Dir
if len(sys.argv) > 1:
    fileDir = sys.argv[1]
else:
    fileDir = 'top'


# config
_NEW_PREFIX = "new"
_ENABLE_LOGGING = True
_IGNORE = ['.db', '.txt', '.rar', '.zip']

def configLogging():
    if not _ENABLE_LOGGING:
        return
    _messagefmt = '[%(asctime)s] %(message)s'
    logging.basicConfig(level=logging.INFO,
                    format=_messagefmt,
                    filename='transform.log',
                    filemode='a')
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    formatter = logging.Formatter(fmt=_messagefmt)
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

def output(str):
    if _ENABLE_LOGGING:
        logging.info(str)
    else:
        print(str)


class Task:
    def __init__(self, oldpath, newpath, press = 50):
        self.oldpath = oldpath
        self.newpath = newpath
        if press <= 0 or press > 100:
            press = 50
        self.press = press
        
def GetTask():
    _threadLock.acquire()
    task = ""
    if len(_taskList) > 0:
        task = _taskList[0]
        _taskList.remove(task)
    
    _threadLock.release()
    return task

def AddTask(oldpath, newpath, press = 50):
    global _allTask
    task = Task(oldpath, newpath, press)
    _taskList.append(task)
    _allTask += 1


_threadLock = threading.Lock()
_taskList = []
_allTask = 0
_done = 0


def generateTask():
    _walk = os.walk(fileDir)
    for root,dirs,files in _walk:
        new_root = root.replace(fileDir , _NEW_PREFIX + fileDir)

        for d in dirs:
            if not os.path.exists(new_root):
                os.mkdir(new_root)
            path = os.path.join(new_root,d)
            #output(path)
            if not os.path.exists(path):
                os.mkdir(path)
        
        for f in files:
            # 跳过指定后缀的文件
            ext = os.path.splitext(f)[-1]
            if ext in _IGNORE:
                continue
            oldpath = os.path.join(root,f)
            newpath = os.path.join(new_root,f)
            if os.path.exists(newpath):
                try :
                    #output('exists : %s' % newpath)
                    pass
                except UnicodeEncodeError as e:
                    output(e)
                continue
            AddTask(oldpath, newpath, 50)


def thread_do_task(id):
    global _done,_allTask

    while _done < _allTask:
        task = GetTask()
        if task == "":
            time.sleep(0.5)
            continue
        try:
            sImage = Image.open(task.oldpath)
        except IOError as e:
            output(e)
            _threadLock.acquire()
            _done += 1
            _threadLock.release()
            continue # 跳过非图像类型的文件
        
        w,h = sImage.size
        dImg = sImage.resize((int(w/2),int(h/2)), Image.ANTIALIAS)
        dImg.save(task.newpath)
        try :
            output('convert : %s   (%d/%d)  threading %d' % (task.newpath, _done,_allTask, id))
        except UnicodeEncodeError as e:
            output(e)
        _threadLock.acquire()
        _done += 1
        _threadLock.release()
        sImage.close()

class myThread (threading.Thread):   #继承父类threading.Thread
    def __init__(self, id):
        threading.Thread.__init__(self)
        self.id = id

    def run(self):                   #把要执行的代码写到run函数里面 线程在创建后会直接运行run函数 
        thread_do_task(self.id)
        


def doAllTask():
    threads = []

    for i in range(15):
        thread = myThread(i)
        thread.start()
        threads.append(thread)

    for t in threads:
        t.join()

if __name__ == "__main__":
    configLogging()

    _time_start = time.clock()
    _time_end   = 0

    generateTask()
    doAllTask()

    _time_end = time.clock()
    _time_used = _time_end - _time_start
    _average = 0 if _allTask == 0 else (_time_used/_allTask)

    output("Multithreading Mode:")
    output("All done! used time %.2fs" % _time_used)
    output("%.2fs per image" % _average)
    output("All Task : %d" % _allTask)