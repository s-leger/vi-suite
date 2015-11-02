import os, bpy, subprocess
from subprocess import PIPE, Popen
from os import rename
from .vi_func import processf

def envi_sim(calc_op, node, connode):
    scene, err = bpy.context.scene, 0
    os.chdir(scene['viparams']['newdir'])
    expand = "-x" if scene['viparams'].get('hvactemplate') else ""
    eidd = os.path.join(os.path.dirname(os.path.abspath(os.path.realpath( __file__ ))), "EPFiles", "Energy+.idd")    
    for frame in range(scene['enparams']['fs'], scene['enparams']['fe'] + 1):
#        shutil.copyfile(os.path.join(scene['viparams']['newdir'], "in{}.epw".format(frame)), os.path.join(scene['viparams']['newdir'], "in.epw"))
    
#        ehtempcmd = "ExpandObjects in.idf"
#        subprocess.call(ehtempcmd, shell = True)
#        subprocess.call('{} {} {}'.format(scene['viparams']['cp'], 'expanded.idf', 'in.idf'), shell = True)
        esimcmd = "EnergyPlus {0} -w in{1}.epw -i {2} -p {3} in{1}.idf".format(expand, frame, eidd, ('{}{}'.format(node.resname, frame), 'eplus{}'.format(frame))[node.resname == '']) 
        esimrun = Popen(esimcmd, shell = True, stdout = PIPE, stderr = PIPE)
        for line in esimrun.stderr:
            if 'EnergyPlus Terminated--Error(s) Detected' in line.decode():
                print(line) 
                calc_op.report({'ERROR'}, "There was an error in the input IDF file. Chect the *.err file in Blender's text editor.")
                err = 1
        for fname in os.listdir('.'):
            if fname.split(".")[0] == node.resname:
                os.remove(os.path.join(scene['viparams']['newdir'], fname))
        for fname in os.listdir('.'):
            if fname.split(".")[0] == "eplusout":
                rename(os.path.join(scene['viparams']['newdir'], fname), os.path.join(scene['viparams']['newdir'],fname.replace("eplusout", node.resname)))
        if err:
            return
        processf(calc_op, node)
    node.dsdoy = connode.sdoy # (locnode.startmonthnode.sdoy
    node.dedoy = connode.edoy
    if node.resname+".err" not in [im.name for im in bpy.data.texts]:
        bpy.data.texts.load(os.path.join(scene['viparams']['newdir'], node.resname+".err"))
    calc_op.report({'INFO'}, "Calculation is finished.")  
            
   