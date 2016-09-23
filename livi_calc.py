# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import bpy, os, datetime
from subprocess import Popen, PIPE
from time import sleep
from . import livi_export
from .vi_func import retpmap, selobj, progressbar, progressfile

def radfexport(scene, export_op, connode, geonode, frames):
    for frame in frames:
        livi_export.fexport(scene, frame, export_op, connode, geonode, pause = 1)

def li_calc(calc_op, simnode, simacc, **kwargs): 
    scene = bpy.context.scene
    pfs, epfs = [], []
    context = simnode['coptions']['Context']
    subcontext = simnode['coptions']['Type']
    scene['liparams']['maxres'], scene['liparams']['minres'], scene['liparams']['avres'] = {}, {}, {}
    frames = range(scene['liparams']['fs'], scene['liparams']['fe'] + 1) if not kwargs.get('genframe') else [kwargs['genframe']]
    os.chdir(scene['viparams']['newdir'])
    rtcmds, rccmds = [], []
    builddict = {'0': ('School', 'Higher Education', 'Healthcare', 'Residential', 'Retail', 'Office & Other'), '2': ('School', 'Higher Education', 'Healthcare', 'Residential', 'Retail', 'Office & Other'), '3': ('Office/Education/Commercial', 'Healthcare')}
    
    for f, frame in enumerate(frames):
        if context == 'Basic' or (context == 'CBDM' and subcontext == '0') or (context == 'Compliance' and int(subcontext) < 3):
#        if context == 'Basic' or (context == 'Compliance' and int(subcontext) < 3):

            if os.path.isfile("{}-{}.af".format(scene['viparams']['filebase'], frame)):
                os.remove("{}-{}.af".format(scene['viparams']['filebase'], frame))
            if simnode.pmap:
                pmappfile = open(os.path.join(scene['viparams']['newdir'], 'viprogress'), 'w')
                pmappfile.close()
                errdict = {'fatal - too many prepasses, no global photons stored\n': "Too many prepasses have ocurred. Make sure light sources can see your geometry",
                'fatal - too many prepasses, no global photons stored, no caustic photons stored\n': "Too many prepasses have ocurred. Turn off caustic photons and encompass the scene",
               'fatal - zero flux from light sources\n': "No light flux, make sure there is a light source and that photon port normals point inwards",
               'fatal - no light sources\n': "No light sources. Photon mapping does not work with HDR skies"}
                amentry, pportentry, cpentry, cpfileentry = retpmap(simnode, frame, scene)
                pmcmd = ('mkpmap -e {1}.pmapmom -bv+ +fo -apD 0.001 {0} -apg {1}-{2}.gpm {3} {4} {5} {1}-{2}.oct'.format(pportentry, scene['viparams']['filebase'], frame, simnode.pmapgno, cpentry, amentry))                   
                pmrun = Popen(pmcmd.split(), stderr = PIPE, stdout = PIPE)
                while pmrun.poll() is None:
                    with open(os.path.join(scene['viparams']['newdir'], 'viprogress'), 'r') as pfile:
                        if 'CANCELLED' in pfile.read():
                            pmrun.kill()
                            return 'CANCELLED'
                        sleep(1)
                        
                with open('{}.pmapmon'.format(scene['viparams']['filebase']), 'r') as pmapfile:
                    for line in pmapfile.readlines():
                        if line in errdict:
                            calc_op.report({'ERROR'}, errdict[line])
                            return
                    
#                for line in pmrun.stdout: 
#                    print(line)
#                for line in pmrun.stderr: 
#                    print(line)
#                    if line.decode() in errdict:
#                        calc_op.report({'ERROR'}, errdict[line.decode()])
#                        return
                

                rtcmds.append("rtrace -n {0} -w {1} -ap {2}-{3}.gpm 50 {4} -faa -h -ov -I {2}-{3}.oct".format(scene['viparams']['nproc'], simnode['radparams'], scene['viparams']['filebase'], frame, cpfileentry)) #+" | tee "+lexport.newdir+lexport.fold+self.simlistn[int(lexport.metric)]+"-"+str(frame)+".res"
            else:
#                if context == 'Compliance':
#                    rtcmds.append("rcontrib -w -n {} {} -m sky_glow -I+ -V+ {}-{}.oct ".format(scene['viparams']['nproc'], simnode['radparams'], scene['viparams']['filebase'], frame))    
#
#                else:
                rtcmds.append("rtrace -n {0} -w {1} -faa -h -ov -I {2}-{3}.oct".format(scene['viparams']['nproc'], simnode['radparams'], scene['viparams']['filebase'], frame)) #+" | tee "+lexport.newdir+lexport.fold+self.simlistn[int(lexport.metric)]+"-"+str(frame)+".res"
        else:
            rccmds.append("rcontrib -w  -h -I -fo -bn 146 {} -n {} -f tregenza.cal -b tbin -m sky_glow {}-{}.oct".format(simnode['radparams'], scene['viparams']['nproc'], scene['viparams']['filebase'], frame))
#            rccmds.append("rcontrib -w  -h -I- -fo -bn 146 {} -n {} -f tregenza.cal -b tbin -m env_glow {}-{}.oct".format(simnode['radparams'], scene['viparams']['nproc'], scene['viparams']['filebase'], frame))

    try:
        tpoints = [bpy.data.objects[lc]['rtpnum'] for lc in scene['liparams']['livic']]
    except:
        calc_op.report({'ERROR'}, 'Re-export the LiVi geometry')
        return
        
    calcsteps = sum(tpoints) * len(frames)
    pfile = progressfile(scene, datetime.datetime.now(), calcsteps)
    kivyrun = progressbar(os.path.join(scene['viparams']['newdir'], 'viprogress'))
    reslists = []

    for oi, o in enumerate([scene.objects[on] for on in scene['liparams']['livic']]):
        curres = sum(tpoints[:oi])
        selobj(scene, o)
        o['omax'], o['omin'], o['oave'], totsensearea, totsdaarea, totasearea  = {}, {}, {}, 0, 0, 0
        if context == 'Basic':
            bccout = o.basiccalcapply(scene, frames, rtcmds, simnode, curres, pfile)
            if bccout == 'CANCELLED':
                return 'CANCELLED'
            else:
                reslists += bccout
                
        elif context == 'CBDM' and subcontext == '0':
            lhout = o.lhcalcapply(scene, frames, rtcmds, simnode, curres, pfile)
            if lhout  == 'CANCELLED':
                return 'CANCELLED'
            else:
                reslists += lhout
        
        elif (context == 'CBDM' and subcontext in ('1', '2')) or (context == 'Compliance' and subcontext == '3'):
            udiout = o.udidacalcapply(scene, frames, rccmds, simnode, curres, pfile)
            if udiout == 'CANCELLED':
                return 'CANCELLED'
            else:
                reslists += udiout[2]
                pfs.append(udiout[0])
                epfs.append(udiout[1])

        elif context == 'Compliance':
            compout = o.compcalcapply(scene, frames, rtcmds, simnode, curres, pfile)  
            if compout == 'CANCELLED':
                return 'CANCELLED'
            else:
                reslists += compout[2]
                pfs.append(compout[0])
                epfs.append(compout[1])
                
    for f, frame in enumerate(frames):
        if context == 'Compliance':
            tpf = 'FAIL' if 'FAIL' in pfs[f] or 'FAIL*' in pfs[f] else 'PASS'
            if simnode['coptions']['canalysis'] == '0': 
                tpf = 'EXEMPLARY' if tpf == 'PASS' and ('FAIL' not in epfs[f] and 'FAIL*' not in epfs[f]) else tpf
                cred = '0' if tpf == 'FAIL' else ('1', '2', '2', '1', '1', '1')[int(simnode['coptions']['buildtype'])]
                ecred = '1' if tpf == 'EXEMPLARY' else '0'
                simnode['tablecomp{}'.format(frame)] = [['Standard: BREEAM HEA1'], 
                        ['Build type: {}'.format(builddict[simnode['coptions']['canalysis']][int(simnode['coptions']['buildtype'])])], [''], ['Standard credits: ' + cred], 
                         ['Exemplary credits: '+ ecred]]
            
            elif simnode['coptions']['canalysis'] == '1':
                cfshcred = 0
                for pf in pfs[f]:
                    for stype in [0, 1, 2]:
                        if all([p[1] == 'Pass' for p in pf if p[0] == stype]) and [p for p in pf if p[0] == stype]:
                            cfshcred += 1
                    simnode['tablecomp{}'.format(frame)] = [['Standard: CfSH'], 
                            ['Build type: Residential'], [''], ['Standard credits: {}'.format(cfshcred)]]
            
            elif simnode['coptions']['canalysis'] == '2':
                gscred = max(len(p) for p in pfs[f]) - max([sum([(0, 1)[p == 'Fail'] for p in pf]) for pf in pfs[f]])
                simnode['tablecomp{}'.format(frame)] = [['Standard: Green Star'], 
                            ['Build type: {}'.format(builddict[simnode['coptions']['canalysis']][int(simnode['coptions']['buildtype'])])], [''], ['Standard credits: {}'.format(gscred)]]

            elif simnode['coptions']['canalysis'] == '3':
                cred = 0
                for z in list(zip(pfs[f], epfs[f])):
                    if all([pf == 'Pass' for pf in z[:-1]]):
                        cred += int(z[-1])
                    simnode['tablecomp{}'.format(frame)] = [['Standard: LEEDv4'], 
                            ['Build type: {}'.format(builddict[simnode['coptions']['canalysis']][int(simnode['coptions']['buildtype'])])], [''], ['Credits: {}'.format(cred)]]
                
    if kivyrun.poll() is None:
        kivyrun.kill()
        
    return reslists
            

