
import os
import sys

print('Please input path : ')
path = input()
print('Please input offset : ')
offset = int(input())

raw = [ os.path.join(path,x) for x in os.listdir(path) if os.path.splitext(x)[-1] != '.py']
new = []

for x in raw:
    name,ext = os.path.splitext(x)
    dir, name = name.rsplit('\\',1)
    new.append('{}\\{:0>3d}{}'.format(dir, int(name)+offset, ext))

raw.reverse()
new.reverse()

print(raw)
print(new)

for i in range(0, len(raw)):
	os.rename(raw[i], new[i])