
import os
from PIL import Image

walk = os.walk('F:\\Download\\top\\')


for root,dirs,files in walk:
    new_root = root.replace('top', 'newtop')

    for d in dirs:
        if not os.path.exists(new_root):
            os.mkdir(new_root)
        path = os.path.join(new_root,d)
        #print(path)
        if not os.path.exists(path):
            os.mkdir(path)
    
    for f in files:
        oldpath = os.path.join(root,f)
        newpath = os.path.join(new_root,f)
        if os.path.exists(newpath):
            try :
                print('exists : %s' % newpath)
            except UnicodeEncodeError as e:
                print(e)
            continue
        sImage = Image.open(oldpath)
        w,h = sImage.size
        dImg = sImage.resize((int(w/2),int(h/2)), Image.ANTIALIAS)
        dImg.save(newpath)
        try :
            print('convert : %s' % newpath)
        except UnicodeEncodeError as e:
            print(e)
    

