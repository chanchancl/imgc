# imgc - images compress
A script for compressing images

# Usages
$ compress.py destdir [rate]

required:
* destdir : include all image dir

optional:
* rate    : compress rate, default 60% (new witdh/ old width, as well as height)

# Example

```
a :  b : 1.jpg 
         2.jpg  
     c : 1.png 
         2.png 

after runing 

new a :  b : 1.jpg
             2.jpg
         c : 1.png
             2.png
```
