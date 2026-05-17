import os, struct

d = "/home/mark/Code/ROMHacking/games/Persona2IS/extrac/D/"
for f in sorted(os.listdir(d)):
    path = os.path.join(d, f)
    size = os.path.getsize(path)
    if 30000 < size < 600000:
        with open(path, "rb") as fp:
            header = fp.read(16).hex()
        print(f"{f:20s}  {size:8d}  {header}")
