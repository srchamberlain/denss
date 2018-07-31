#!/usr/bin/env python
#
#    denss.all.py
#    Generate, align, and average many electron density maps from solution scattering data.
#
#    Part of DENSS
#    DENSS: DENsity from Solution Scattering
#    A tool for calculating an electron density map from solution scattering data
#
#    Tested using Anaconda / Python 2.7
#
#    Authors: Thomas D. Grant, Nhan D. Nguyen
#    Email:  <tgrant@hwi.buffalo.edu>, <ndnguyen20@wabash.edu>
#    Copyright 2018 The Research Foundation for SUNY
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import numpy as np
from scipy import ndimage
from multiprocessing import Pool
import imp, logging, sys, argparse, os, copy, time
from saxstats._version import __version__
import saxstats.saxstats as saxs
from functools import partial
import saxstats.denssopts as dopts

#have to run parser twice, first just to get filename for loadProfile
#then have to run it after deciding what the correct dmax should be
#so that the voxel size, box size, nsamples, etc are set correctly
initparser = argparse.ArgumentParser()
initparser.add_argument("-nm", "--nmaps",default = 20,type =int, help="Number of maps to be generated (default 20)")
initparser.add_argument("-j", "--cores", type=int, default = 1, help="Number of cores used for parallel processing. (default: 1)")
initparser.add_argument("-en_on", "--enantiomer_on", action = "store_true", dest="enan", help="Generate and select best enantiomers (default). ")
initparser.add_argument("-en_off", "--enantiomer_off", action = "store_false", dest="enan", help="Do not generate and select best enantiomers.")
initparser.add_argument("-ref", "--ref", default=None, type=str, help="Input reference model (.mrc or .pdb file, optional).")
initparser.add_argument("-c_on", "--center_on", dest="center", action="store_true", help="Center reference PDB map.")
initparser.add_argument("-c_off", "--center_off", dest="center", action="store_false", help="Do not center reference PDB map (default).")
initparser.add_argument("-r", "--resolution", default=15.0, type=float, help="Resolution of map calculated from reference PDB file (default 15 angstroms).")
initparser.set_defaults(enan = True)
initparser.set_defaults(center = True)
initargs = dopts.parse_arguments(initparser, gnomdmax=None)

q, I, sigq, dmax, isout = saxs.loadProfile(initargs.file)

if dmax <= 0:
    dmax = None

parser = argparse.ArgumentParser()
parser.add_argument("-nm", "--nmaps",default = 20,type =int, help="Number of maps to be generated (default 20)")
parser.add_argument("-j", "--cores", type=int, default = 1, help="Number of cores used for parallel processing. (default: 1)")
parser.add_argument("-en_on", "--enantiomer_on", action = "store_true", dest="enan", help="Generate and select best enantiomers (default). ")
parser.add_argument("-en_off", "--enantiomer_off", action = "store_false", dest="enan", help="Do not generate and select best enantiomers.")
parser.add_argument("-ref", "--ref", default=None, type=str, help="Input reference model (.mrc or .pdb file, optional).")
parser.add_argument("-c_on", "--center_on", dest="center", action="store_true", help="Center reference PDB map.")
parser.add_argument("-c_off", "--center_off", dest="center", action="store_false", help="Do not center reference PDB map (default).")
parser.add_argument("-r", "--resolution", default=15.0, type=float, help="Resolution of map calculated from reference PDB file (default 15 angstroms).")
parser.set_defaults(enan = True)
parser.set_defaults(center = True)
superargs = dopts.parse_arguments(parser, gnomdmax=dmax)

args = copy.copy(superargs)
del args.cores
del args.enan
del args.ref
del args.nmaps
del args.file
del args.plot
del args.nsamples
del args.mode
del args.resolution
del args.center

if superargs.nmaps<2:
    print "Not enough maps to align"
    sys.exit(1)

basename, ext = os.path.splitext(superargs.file)
if (superargs.output is None) or (superargs.output == basename):
    output = basename
else:
    output = superargs.output

dir = output
dirn = 0
while os.path.isdir(dir):
    dir = output + "_" + str(dirn)
    dirn += 1

print dir
os.mkdir(dir)
output = dir+'/'+dir
args.output = output
superargs.output = output

fname = output+'_final.log'
superlogger = logging.getLogger("")
superlogger.setLevel(logging.INFO)
fh = logging.FileHandler(fname)
formatter = logging.Formatter('%(asctime)s - %(message)s')
fh.setFormatter(formatter)
superlogger.addHandler(fh)

logging.info('BEGIN')
logging.info('DENSS Version: %s', __version__)
logging.info('Data filename: %s', superargs.file)
logging.info('Enantiomer selection: %r', superargs.enan)

denss_inputs = {'I':I,'sigq':sigq,'q':q}

for arg in vars(args):
    denss_inputs[arg]= getattr(args, arg)

quiet = np.ones(superargs.nmaps,dtype=bool)
quiet[::superargs.nmaps] = False

def multi_denss(niter, **kwargs):
    try:
        global quiet
        kwargs['output'] = kwargs['output'] +'_'+str(niter)
        np.random.seed(niter+int(time.time()))
        kwargs['seed'] = np.random.randint(2**31-1)
        kwargs['quiet'] = quiet[niter]
        if (not kwargs['quiet']) and (niter==superargs.nmaps-1):
            print '\n'
        if niter<=superargs.nmaps-1:
            sys.stdout.write( "\r Running denss job: %i / %i " % (niter+1,superargs.nmaps))
            sys.stdout.flush()
        
        fname = kwargs['output']+'.log'
        logger = logging.getLogger("")
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(fname)
        formatter = logging.Formatter('%(asctime)s - %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
        #logging.basicConfig(filename=kwargs['output']+'.log',level=logging.INFO,filemode='w',
        #                    format='%(asctime)s %(message)s', datefmt='%Y-%m-%d %I:%M:%S %p')
        logging.info('BEGIN')
        logging.info('DENSS Version: %s', __version__)
        logging.info('Data filename: %s', superargs.file)
        logging.info('Output prefix: %s', kwargs['output'])
        logging.info('Mode: %s', superargs.mode)
        result= saxs.denss(**kwargs)
        logging.info('END')
        return result
        time.sleep(1)
    except KeyboardInterrupt:
        pass

pool = Pool(superargs.cores)

try:
    mapfunc = partial(multi_denss, **denss_inputs)
    denss_outputs = pool.map(mapfunc, range(superargs.nmaps))
    print "\r Finishing denss job: %i / %i" % (superargs.nmaps,superargs.nmaps)
    sys.stdout.flush()
    pool.close()
    pool.join()
except KeyboardInterrupt:
    pool.terminate()
    pool.close()
    sys.exit(1)

qdata = denss_outputs[0][0]
Idata = denss_outputs[0][1]
sigqdata = denss_outputs[0][2]
qbinsc = denss_outputs[0][3]
all_Imean = [denss_outputs[i][4] for i in np.arange(superargs.nmaps)]
header = ['q','I','error']
fit = np.zeros(( len(qbinsc),superargs.nmaps+3 ))
fit[:len(qdata),0] = qdata
fit[:len(Idata),1] = Idata
fit[:len(sigqdata),2] = sigqdata

for map in range(superargs.nmaps):
    fit[:len(all_Imean[0]),map+3] = all_Imean[map]
    header.append("I_fit_"+str(map))

np.savetxt(output+'_map.fit',fit,delimiter=" ",fmt="%.5e", header=" ".join(header))
chi_header, rg_header, supportV_header = zip(*[('chi_'+str(i), 'rg_'+str(i),'supportV_'+str(i)) for i in range(superargs.nmaps)])
all_chis = np.array([denss_outputs[i][5] for i in np.arange(superargs.nmaps)])
all_rg = np.array([denss_outputs[i][6] for i in np.arange(superargs.nmaps)])
all_supportV = np.array([denss_outputs[i][7] for i in np.arange(superargs.nmaps)])

np.savetxt(output+'_chis_by_step.fit',all_chis.T,delimiter=" ",fmt="%.5e",header=",".join(chi_header))
np.savetxt(output+'_rg_by_step.fit',all_rg.T,delimiter=" ",fmt="%.5e",header=",".join(rg_header))
np.savetxt(output+'_supportV_by_step.fit',all_supportV.T,delimiter=" ",fmt="%.5e",header=",".join(supportV_header))

allrhos = np.array([denss_outputs[i][8] for i in np.arange(superargs.nmaps)])
sides = np.array([denss_outputs[i][9] for i in np.arange(superargs.nmaps)])

#split rhos into two halves randomly
#reason: allrhos[0] is used as the initial reference for aligning and selecting
#enantiomers. This allows one to run it again if desired to use a different
#initial reference. The enantiomers are then used to determine a new reference
#using the binary average procedure. We can't use the binary average procedure
#prior to enantiomer selection, because the resulting average will likely
#average out any handedness.

set1 = np.random.choice(range(allrhos.shape[0]), allrhos.shape[0]/2, replace=False)
set2 = np.setdiff1d(np.arange(allrhos.shape[0]), set1)
index = np.concatenate((set1,set2))
allrhos = np.array([allrhos[i] for i in index])
sides = np.array([sides[i] for i in index])

if superargs.ref is not None:
    #allow input of reference structure
    if superargs.ref.endswith('.pdb'):
        refside = sides[0]
        voxel = (refside/allrhos[0].shape)[0]
        halfside = refside/2
        n = int(refside/voxel)
        dx = refside/n
        x_ = np.linspace(-halfside,halfside,n)
        x,y,z = np.meshgrid(x_,x_,x_,indexing='ij')
        xyz = np.column_stack((x.ravel(),y.ravel(),z.ravel()))
        pdb = saxs.PDB(superargs.ref)
        if superargs.center:
            pdb.coords -= pdb.coords.mean(axis=0)
        refrho = saxs.pdb2map_gauss(pdb,xyz=xyz,sigma=superargs.resolution)
        refrho = refrho*np.sum(allrhos[0])/np.sum(refrho)
    
    if superargs.ref.endswith('.mrc'):
        refrho, refside = saxs.read_mrc(superargs.ref)

if superargs.enan:
    if superargs.ref is None:
        #we need to use a single map to select enantiomers
        #however, a single map doesn't result in the best alignments to generate
        #the reference for the final averaging. So, lets first get a slightly
        #better initial reference by averaging a few (a third) of the maps
        #that have already been roughly aligned through enantiomer selection,
        #then use that average as the initial reference for binary averaging,
        #which then produces the actual reference for the final alignment step.
        #irefrho = initial refrho
        irefrhos, scores = saxs.align_multiple(allrhos[0], allrhos, superargs.cores)
        order = np.argsort(-scores)
        irefrhos = irefrhos[order]
        if superargs.nmaps<=3:
            irefrho = np.mean(irefrhos, axis =0)
        else:
            irefrho = np.mean(irefrhos[:int(allrhos.shape[0]/3)], axis=0)
    else:
        irefrho = refrho

if superargs.enan:
    print "Generating enantiomers..."
    allrhos, scores = saxs.select_best_enantiomers(irefrho, allrhos, superargs.cores)

if superargs.ref is None:
    refrho = saxs.binary_average(allrhos, superargs.cores)

aligned, scores = saxs.align_multiple(refrho, allrhos, superargs.cores)

#filter rhos with scores below the mean - 2*standard deviation.
mean = np.mean(scores)
std = np.std(scores)
threshold = mean - 2*std
filtered = np.empty(len(scores),dtype=str)
print "Mean of correlation scores: %.3f" % mean
print "Standard deviation of scores: %.3f" % std
for i in index:
    if scores[i] < threshold:
        filtered[i] = 'Filtered'
    else:
        filtered[i] = ' '
    ioutput = output+"_"+str(i)+"_aligned"
    saxs.write_mrc(aligned[i], sides[0], ioutput+".mrc")
    print "%s.mrc written. Score = %0.3f %s " % (ioutput,scores[i],filtered[i])
    logging.info('Correlation score to reference: %s.mrc %.3f %s', ioutput, scores[i], filtered[i])

aligned = aligned[scores>threshold]
average_rho = np.mean(aligned,axis=0)

logging.info('Mean of correlation scores: %.3f', mean)
logging.info('Standard deviation of the scores: %.3f', std)
logging.info('Total number of input maps for alignment: %i',allrhos.shape[0])
logging.info('Number of aligned maps accepted: %i', aligned.shape[0])
logging.info('Correlation score between average and reference: %.3f', 1/saxs.rho_overlap_score(average_rho, refrho))
saxs.write_mrc(average_rho, sides[0], output+'_average.mrc')

#split maps into 2 halves--> enan, align, average independently with same refrho
avg_rho1 = np.mean(aligned[::2],axis=0)
avg_rho2 = np.mean(aligned[1::2],axis=0)
fsc = saxs.calc_fsc(avg_rho1,avg_rho2,sides[0])
np.savetxt(args.output+'_fsc.dat',fsc,delimiter=" ",fmt="%.5e",header="qbins, FSC")
x = np.linspace(fsc[0,0],fsc[-1,0],100)
y = np.interp(x, fsc[:,0], fsc[:,1])
resi = np.argmin(y>=0.5)
resx = np.interp(0.5,[y[resi+1],y[resi]],[x[resi+1],x[resi]])
resn = round(float(1./resx),1)
print "Resolution: %.1f" % resn, u'\u212B'.encode('utf-8')

logging.info('Resolution: %.1f '+ u'\u212B'.encode('utf-8'), resn )
logging.info('END')












