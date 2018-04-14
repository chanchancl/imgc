
import os
import sys
import time
import logging
import pathlib
import asyncio
import argparse
import threading
from PIL import Image


_LOGGING_FILE = 'Transform.log'
_NEW_PREFIX = 'new '

# config the logging
def configLogging():
    # get logger and set level
    rootLogger = logging.getLogger()
    rootLogger.setLevel(logging.INFO)

    # formatters
    consoleFormatter = logging.Formatter('[%(asctime)s] %(message)s')
    fileFormatter = logging.Formatter('%(levelname)s [%(asctime)s] %(message)s')

    # handlers
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(consoleFormatter)
    console.setLevel(logging.INFO)

    logfile = logging.FileHandler(_LOGGING_FILE, 'a', encoding='utf-8')
    logfile.setFormatter(fileFormatter)
    logfile.setLevel(logging.INFO)

    rootLogger.addHandler(console)
    rootLogger.addHandler(logfile)


# filein : path of image file [in]
# fileout : path of image file [out]
# rate : float
def CompressImage(filein, fileout, rate):
    image = Image.open(filein)

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
        logging.debug('transform {}'.format(self.fin))

    
class TransformManager:
    dir = None
    tList = None
    bytesBeforecompress = 0
    bytesAftercompress = 0
    ignoreExt = None
    rate = 1.0
    
    def __init__(self, dir, ignoreExt = [], rate=0.6):
        self.dir = dir
        self.tList = []
        self.ignoreExt = ignoreExt
        self.rate = rate
    
    def ScanDir(self):
        for root, dirs, files in os.walk(self.dir):
            try:
                rt, oth = root.split('\\', 1)
                rt = _NEW_PREFIX + rt
                newroot = os.path.join(rt,oth)
            except ValueError:
                newroot = root.replace(self.dir, _NEW_PREFIX + self.dir)

            # scan all dirs
            # change root and create same dir trees
            r'''
                z\b\            x\b\
                 \c\     ->      \c\
                 \d\             \d\
            '''
            for dir in dirs:
                if not os.path.exists(newroot):
                    os.mkdir(newroot)
                    
                newdir = os.path.join(newroot, dir)

                if not os.path.exists(newdir):
                    os.mkdir(newdir)
                logging.debug('newdir {}'.format(newdir))
            
            for file in files:
                ext = os.path.splitext(file)[-1]
                # filter and ignore
                if ext in self.ignoreExt:
                    continue

                oldfile = os.path.join(root,file)
                newfile = os.path.join(newroot, file)
                logging.debug("find filter file {}, translate it to {}".format(oldfile,newfile))

                trans = Transform(oldfile, newfile, self.rate)
                self.tList.append(trans)
        
        logging.info('Scan files : {}'.format(len(self.tList)))

    def TransformAll(self):
        self.meta = {
            'all'    : len(self.tList),
            'done'   : 0,
            'exists' : 0,
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
                    logging.error('{} is truncated'.format(e.filename))
                    meta['errors'] += 1
                except OSFileExists as e:
                    logging.debug('{} is exists'.format(e.filename))
                    self.bytesAftercompress += os.path.getsize(trans.fout)
                    meta['exists'] += 1

                proc = meta['done']+meta['errors']+meta['exists']
                if proc % 100 == 0:
                    logging.info('({}/{}) have processed.'.format(proc,meta['all']))

            logging.info('SingleThread done   : {}'.format(meta['done']))
            logging.info('SingleThread exists : {}'.format(meta['exists']))
            logging.info('SingleThread errors : {}'.format(meta['errors']))

        def MultiThread():
            tList = self.tList.copy()
            def GetTransform():
                if len(tList):
                    trans = tList[0]
                    del(tList[0])
                    return trans
                return None

            def Run(meta):
                trans = GetTransform()

                while trans:
                    self.bytesBeforecompress += os.path.getsize(trans.fin)
                    try:
                        trans.DoTransform()
                        meta['done'] += 1
                        self.bytesAftercompress += os.path.getsize(trans.fout)
                    except OSError as e:
                        logging.error('{} is truncated'.format(e.filename))
                        meta['errors'] += 1
                    except OSFileExists as e:
                        logging.debug('{} is exists'.format(e.filename))
                        self.bytesAftercompress += os.path.getsize(trans.fout)
                        meta['exists'] += 1
                    
                    proc = meta['done']+meta['errors']+meta['exists']
                    if proc % 100 == 0:
                        logging.info('({}/{}) have processed.'.format(proc,meta['all']))
                    trans = GetTransform()
                            
            threads = [threading.Thread(target=Run, args=(self.meta,)) for _ in range(10)]

            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            logging.info('MultiThread done   : {}'.format(self.meta['done']))
            logging.info('MultiThread exists : {}'.format(self.meta['exists']))
            logging.info('MultiThread errors  : {}'.format(self.meta['errors']))

        def Asyncio():
            meta = self.meta
            async def Run(trans, meta):
                self.bytesBeforecompress += os.path.getsize(trans.fin)
                try:
                    trans.DoTransform()
                    meta['done'] += 1
                    self.bytesAftercompress += os.path.getsize(trans.fout)
                except OSError as e:
                    logging.error('{} is truncated'.format(e.filename))
                    meta['errors'] += 1
                except OSFileExists as e:
                    logging.debug('{} is exists'.format(e.filename))
                    self.bytesAftercompress += os.path.getsize(trans.fout)
                    meta['exists'] += 1
                
                proc = meta['done']+meta['errors']+meta['exists']
                if proc % 100 == 0:
                    logging.info('({}/{}) have processed.'.format(proc,meta['all']))

            tasks = [Run(trans, self.meta) for trans in self.tList]
            loop = asyncio.get_event_loop()
            loop.run_until_complete(asyncio.wait(tasks))
            loop.close()
            logging.info('Asyncio done   : {}'.format(meta['done']))
            logging.info('Asyncio exists : {}'.format(meta['exists']))
            logging.info('Asyncio errors : {}'.format(meta['errors']))
        
        #SingleThread()
        MultiThread()
        #Asyncio()


def main(destDir, rate=0.6):
    configLogging()
    logging.info('#'*79)
    logging.info('Trnasform Start!')
    mgr = TransformManager(destDir, ['rar', 'txt', 'db'], rate)

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

    logging.info('Transform Info : ')
    logging.info('BeforeCompress : {:>6.2f} MB'.format(mgr.bytesBeforecompress/1024/1024))
    logging.info('AfterCompress  : {:>6.2f} MB'.format(mgr.bytesAftercompress/1024/1024))
    logging.info('scan time  : {:>6.3f} s'.format(scanEnd-scanStart))
    logging.info('trans time : {:>6.3f} s'.format(transEnd-transStart))
    if len(mgr.tList) != 0:
        logging.info('average {:>6.4f} s per image'.format((transEnd-transStart)/len(mgr.tList)))

    logging.info('#'*79 +'\n')



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Compress your images.')
    parser.add_argument('destDir', help='the dir you want compress.')
    parser.add_argument('-r', '--rate', default=0.6, type=float)

    args = parser.parse_args()
    main(args.destDir, args.rate)