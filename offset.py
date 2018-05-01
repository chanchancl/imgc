
import os
import sys

if len(sys.argv) == 1 :
    print('Please input offset')
    sys.exit(0)

offset = int(sys.argv[1])


raw = [x for x in os.listdir() if os.path.splitext(x)[-1] != '.py' ]
new = []

for x in raw:
    name,ext = os.path.splitext(x)
    new.append('{:0>3d}{}'.format(int(name)+offset, ext))

raw.reverse()
new.reverse()

print(raw)
print(new)

for i in range(0, len(raw)):
	os.rename(raw[i], new[i])