import os
import sys
import time
import logging
import pathlib
import asyncio
import argparse
import threading
from PIL import Image

_LOGGING_FILE = 'logfile.log'
_NEW_PREFIX = 'new '

# config the logging
def configLogging():
    # get logger and set level
    rootLogger = logging.getLogger()
    rootLogger.setLevel(logging.DEBUG)

    # formatters
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(message)s')

    # handlers
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.setLevel(logging.INFO)

    logfile = logging.FileHandler(_LOGGING_FILE, 'a', encoding='utf-8')
    logfile.setFormatter(formatter)
    logfile.setLevel(logging.INFO)

    rootLogger.addHandler(console)
    rootLogger.addHandler(logfile)
    
def _mkdir(path):
    if not os.path.exists(path):
        os.mkdir(path)

__loggingINFO = logging.info
def _logging(msg):
    __loggingINFO(' ' + msg)
logging.info = _logging
        

_fileSize = {}
        
def GetFileSize(filePath):
    if filePath in _fileSize:
        return _fileSize[filePath]
    if os.path.exists(filePath):
        size = os.path.getsize(filePath)
        _fileSize[filePath] = size
        return size
    return 0
        
# filein : path of image file [in]
# fileout : path of image file [out]
# rate : float
def CompressImage(filein, fileout, rate):
    with Image.open(filein) as image:
        # 2018.5.1
        # fix bugs, that some pics is opend with mode 'P'
        # and can't save with ext '.jpg'
        if image.mode != 'RGB':
            # 2018.6.18
            # fix bugs, pic with mode L,can't save with mode 'RGB'
            # so translate it to mode 'P' first
            # and I don't know why I must convert twice and must
            # get a exception first.
            if image.mode == 'L':
                try:
                    image = image.convert('P')
                except Exception:
                    image = image.convert('P')
            image = image.convert('RGB')

        w,h = image.size
        w,h = map(int,[w*rate,h*rate])

        output = image.resize((w,h),Image.ANTIALIAS)
        output.save(fileout)
        
 
class OSFileExists(Exception):
    def __init__(self, file):
        self.filename = file

class Transform:
    fin  = None
    fout = None
    rate = None
    def __init__(self, fold, fnew, rate=0.6):
        self.fin = fold
        self.fout = fnew
        self.rate = rate
    
    def DoTransform(self):
        if os.path.exists(self.fout):
            raise OSFileExists(self.fout)
            
        CompressImage(self.fin, self.fout, self.rate)
        logging.debug('  transform {}'.format(self.fin))

    
class TransformManager:
    dir = None
    tList = None
    nExists = 0
    bytesBeforecompress = 0
    bytesAllBeforecompress = 0
    bytesAftercompress = 0
    bytesAllAftercompress = 0
    
    ignoreExt = None
    rate = 1.0
    
    def __init__(self, dir, ignoreExt = [], rate=0.6):
        self.dir = dir
        self.tList = []
        self.ignoreExt = ignoreExt
        self.rate = rate
        self.nExists = 0
    
    def ScanDir(self):
        for root, dirs, files in os.walk(self.dir):
            try:
                # path exists at least 1 '\\'(split)
                rt, oth = root.split('\\', 1)
                rt = _NEW_PREFIX + rt
                newroot = os.path.join(rt,oth)
            except ValueError:
                # there is only 1 root
                newroot = root.replace(self.dir, _NEW_PREFIX + self.dir)

            # scan all dirs
            # change root and create same dir trees
            r'''
                z\b\            x\b\
                 \c\     ->      \c\
                 \d\             \d\
            '''
            for dir in dirs:
                _mkdir(newroot)
                newdir = os.path.join(newroot, dir)
                _mkdir(newdir)
                logging.debug('  newdir {}'.format(newdir))
            
            for file in files:
                ext = os.path.splitext(file)[-1]
                # filter and ignore
                if ext in self.ignoreExt:
                    continue

                oldfile = os.path.join(root,file)
                newfile = os.path.join(newroot, file)
                
                self.bytesAllBeforecompress += os.path.getsize(oldfile)
                if os.path.exists(newfile):
                    self.nExists += 1
                    logging.debug('  find exists file {}'.format(oldfile))
                    self.bytesAllAftercompress += os.path.getsize(newfile)
                    continue
                logging.debug("  find filter file {}".format(oldfile))

                trans = Transform(oldfile, newfile, self.rate)
                self.tList.append(trans)
        
        # 因为从tList中获取元素顺序是倒的，所以在这里也倒一下
        self.tList.reverse()

        logging.info('  Uncompress files : {}'.format(len(self.tList)))
        logging.info('  Exists files     : {}'.format(self.nExists))

    def TransformAll(self):
        self.meta = {
            'all'    : len(self.tList),
            'done'   : 0,
            'exists' : self.nExists,
            'errors' : 0,
        }
        
        def SingleThread():
            for trans in self.tList:
                self.bytesBeforecompress += os.path.getsize(trans.fin)
                meta = self.meta
                try:
                    trans.DoTransform()
                    meta['done'] += 1
                    self.bytesAftercompress += os.path.getsize(trans.fout)
                except OSError as e:
                    logging.error('  {} is truncated'.format(e.filename))
                    meta['errors'] += 1
                    '''except OSFileExists as e:
                    logging.debug('  {} is exists'.format(e.filename))
                    self.bytesAftercompress += os.path.getsize(trans.fout)
                    meta['exists'] += 1'''

                proc = meta['done']+meta['errors']+meta['exists']
                if proc % 100 == 0:
                    logging.info('  ({}/{}) have processed.'.format(proc,meta['all']))

            logging.info('  SingleThread Done   : {}'.format(meta['done']))
            logging.info('  SingleThread Exists : {}'.format(meta['exists']))
            logging.info('  SingleThread Errors : {}'.format(meta['errors']))

        def MultiThread():
            tList = self.tList.copy()
            def GetTransform():
                if len(tList):
                    trans = tList.pop()
                    return trans
                return None

            def Run(meta):
                trans = GetTransform()
                lock = threading.Lock()
                
                while trans:
                    size = os.path.getsize(trans.fin)
                    
                    lock.acquire()
                    self.bytesBeforecompress += size
                    lock.release()
                    try:
                        trans.DoTransform()
                        size = os.path.getsize(trans.fout)
                        
                        lock.acquire()
                        meta['done'] += 1
                        self.bytesAftercompress += size
                        lock.release()

                    except (OSError,IOError):
                        logging.error('  {} is truncated or not a valid pic. '.format(trans.fin))

                        lock.acquire()
                        meta['errors'] += 1
                        lock.release()

                        '''except OSFileExists as e:
                        logging.debug('  {} is exists'.format(e.filename))
                        size = os.path.getsize(trans.fout)'''
                        
                        lock.acquire()
                        meta['exists'] += 1
                        self.bytesAftercompress += size
                        lock.release()
                    
                    lock.acquire()
                    proc = meta['done']+meta['errors']+meta['exists']
                    lock.release()
                    if proc % 100 == 0:
                        logging.info('  ({}/{}) have processed.'.format(proc,meta['all']))
                    
                    trans = GetTransform()
                            
            threads = [threading.Thread(target=Run, args=(self.meta,)) for _ in range(8)]

            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            
            logging.info('  MultiThread Done   : {}'.format(self.meta['done']))
            logging.info('  MultiThread Exists : {}'.format(self.meta['exists']))
            logging.info('  MultiThread Errors : {}'.format(self.meta['errors']))

        def Asyncio():
            meta = self.meta
            async def Run(trans, meta):
                self.bytesBeforecompress += os.path.getsize(trans.fin)
                try:
                    trans.DoTransform()
                    meta['done'] += 1
                    self.bytesAftercompress += os.path.getsize(trans.fout)
                except OSError as e:
                    logging.error('  {} is truncated'.format(e.filename))
                    meta['errors'] += 1
                '''except OSFileExists as e:
                    logging.debug('  {} is exists'.format(e.filename))
                    self.bytesAftercompress += os.path.getsize(trans.fout)
                    meta['exists'] += 1'''
                
                proc = meta['done']+meta['errors']+meta['exists']
                if proc % 100 == 0:
                    logging.info('  ({}/{}) have processed.'.format(proc,meta['all']))

            tasks = [Run(trans, self.meta) for trans in self.tList]
            loop = asyncio.get_event_loop()
            loop.run_until_complete(asyncio.wait(tasks))
            loop.close()
            logging.info('  Asyncio Done   : {}'.format(meta['done']))
            logging.info('  Asyncio Exists : {}'.format(meta['exists']))
            logging.info('  Asyncio Errors : {}'.format(meta['errors']))
        
        #SingleThread()
        MultiThread()
        #Asyncio()
        


def main(destDir, rate=0.6):
    configLogging()
    
    splitLine = '#'*79
    logging.info(splitLine)
    logging.info('Trnasform Start!')
    mgr = TransformManager(destDir, ['.rar', '.txt', '.db', '.py'], rate)

    logging.info('1.Start scanf')
    scanStart = time.time()
    mgr.ScanDir()
    scanEnd = time.time()

    logging.info('2.Start transform')
    transStart = time.time()
    meta = mgr.TransformAll()
    transEnd = time.time()
    
    #unuse, log during transform
    meta = None
    
    scanTime = scanEnd - scanStart
    transTime = transEnd - transStart
    sumTime = scanTime + transTime
    
    x = 1/1024**2
    logging.info('3.Transform Info')
    logging.info('  Scan time  : {:>6.3f} s'.format(scanTime))
    logging.info('  Trans time : {:>6.3f} s'.format(transTime))
    logging.info('  Sum time   : {:>6.3f} s'.format(scanTime + transTime))
    logging.info('  CompressItem Info')
    logging.info('    BeforeCompress : {:>6.2f} MB'.format(mgr.bytesBeforecompress*x))
    logging.info('    AfterCompress  : {:>6.2f} MB'.format(mgr.bytesAftercompress*x))
    if len(mgr.tList) != 0:
        logging.info('    Average {:>6.3f} s per image'.format(sumTime/len(mgr.tList)))
    logging.info('  All Info')
    logging.info('    AllByforeCompress : {:>7.2f} MB'.format(mgr.bytesAllBeforecompress*x))
    logging.info('    AllAfterCompress  : {:>7.2f} MB'.format(mgr.bytesAllAftercompress*x))
    logging.info('    Compress Rate     : {:>7.2f} %'.format(mgr.bytesAllAftercompress/mgr.    bytesAllBeforecompress*100.0))
    logging.info('    All Average {:>6.3f} s per image'.format(sumTime/(len(mgr.tList)+mgr.nExists)))
    

    logging.info(splitLine)



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Compress your images.')
    parser.add_argument('destDir', help='the dir you want compress.')
    parser.add_argument('-r', '--rate', default=0.6, type=float, help='the rate bettween new h/w and raw h/w.')

    args = parser.parse_args()
    main(args.destDir, args.rate)
    