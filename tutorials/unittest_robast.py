#!/usr/bin/env python

import unittest
import ROOT
import array
import time
import ctypes

cm = ROOT.AOpticsManager.cm()
mm = ROOT.AOpticsManager.mm()
um = ROOT.AOpticsManager.um()
nm = ROOT.AOpticsManager.nm()
m  = ROOT.AOpticsManager.m()
rad = ROOT.AOpticsManager.rad()
deg = ROOT.AOpticsManager.deg()

ROOT.gROOT.ProcessLine('std::shared_ptr<TGraph> graph;')
ROOT.gROOT.ProcessLine('std::shared_ptr<TGraph2D> graph2d;')
ROOT.gROOT.ProcessLine('std::shared_ptr<ARefractiveIndex> refidx;')

ROOT.gROOT.ProcessLine('auto air = std::make_shared<ARefractiveIndex>(1., 0.)');
ROOT.gROOT.ProcessLine('std::shared_ptr<ARefractiveIndex> Si = std::make_shared<AFilmetrixDotCom>("Si.txt");');
ROOT.gROOT.ProcessLine('std::shared_ptr<ARefractiveIndex> Si3N4 = std::make_shared<AFilmetrixDotCom>("Si3N4.txt");');
ROOT.gROOT.ProcessLine('std::shared_ptr<ARefractiveIndex> SiO2 = std::make_shared<AFilmetrixDotCom>("SiO2.txt");');
ROOT.gROOT.ProcessLine('std::shared_ptr<ARefractiveIndex> Al = std::make_shared<AFilmetrixDotCom>("Al.txt");');
ROOT.gROOT.ProcessLine('std::shared_ptr<ARefractiveIndex> TiO2 = std::make_shared<AFilmetrixDotCom>("TiO2.txt");');

def makeTheWorld():
    global world, worldbox # avoid automatic deletion and C++ seg fault
    manager = ROOT.AOpticsManager("manager", "manager")
    worldbox = ROOT.TGeoBBox("worldbox", 1*m, 1*m, 1*m)
    world = ROOT.AOpticalComponent("world", worldbox)
    manager.SetTopVolume(world)
    
    return manager

class TestROBAST(unittest.TestCase):
    """
    Unit test for ROBAST
    """
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testAbsorptionLength(self):
        manager = makeTheWorld()

        lensbox = ROOT.TGeoBBox("lensbox", 0.5*m, 0.5*m, 0.5*m)
        lens = ROOT.ALens("lens", lensbox)

        manager.GetTopVolume().AddNode(lens, 1)
        manager.CloseGeometry()
        if ROOT.gInterpreter.ProcessLine('ROOT_VERSION_CODE;') < \
           ROOT.gInterpreter.ProcessLine('ROOT_VERSION(6, 2, 0);'):
            manager.SetMultiThread(True)
        manager.SetMaxThreads(4)

        # test absorption length evaluated from a TGraph
        wl = 400 * nm
        absl = 1 * mm

        ROOT.gROOT.ProcessLine('refidx = std::make_shared<ARefractiveIndex>();')
        ROOT.gROOT.ProcessLine('graph = std::make_shared<TGraph>();')
        ROOT.graph.SetPoint(0, wl, 1)
        ROOT.refidx.SetRefractiveIndex(ROOT.graph)
        ROOT.gROOT.ProcessLine('graph = std::make_shared<TGraph>();')
        k = ROOT.ARefractiveIndex.AbsorptionLengthToExtinctionCoefficient(absl, wl)
        ROOT.graph.SetPoint(0, wl, k)
        ROOT.refidx.SetExtinctionCoefficient(ROOT.graph)
        lens.SetRefractiveIndex(ROOT.refidx)

        rays = ROOT.ARayShooter.RandomSphere(400*nm, 10000)
        manager.TraceNonSequential(rays)
            
        h = ROOT.TH1D("h", "h", 1000, 0, 10)
            
        absorbed = rays.GetAbsorbed()
            
        for i in range(absorbed.GetLast() + 1):
            ray = absorbed.At(i)
            p = array.array("d", [0, 0, 0, 0])
            ray.GetLastPoint(p)
            d = (p[0]*p[0] + p[1]*p[1] + p[2]*p[2])**0.5
            h.Fill(d/mm)
                
        h.Draw()
        h.Fit("expo", "l")
        ROOT.gPad.Update()

        expo = h.GetFunction("expo")
        p = -expo.GetParameter(1)
        e = expo.GetParError(1)

        self.assertGreater(1, p - 3*e)
        self.assertLess(1, p + 3*e)

    def testFresnelReflection(self):
        manager = makeTheWorld()
        manager.DisableFresnelReflection(False) # enable

        lensbox = ROOT.TGeoBBox("lensbox", 0.5*m, 0.5*m, 0.5*m)
        lens = ROOT.ALens("lens", lensbox)

        wl = 400 * nm
        absl = 1 * um
        idx = 3.

        ROOT.gROOT.ProcessLine('double idx, k;')
        ROOT.idx = idx
        ROOT.k = ROOT.ARefractiveIndex.AbsorptionLengthToExtinctionCoefficient(absl, wl)
        ROOT.gROOT.ProcessLine('refidx = std::make_shared<ARefractiveIndex>(idx, k);')
        lens.SetRefractiveIndex(ROOT.refidx)

        manager.GetTopVolume().AddNode(lens, 1)
        manager.CloseGeometry()
        if ROOT.gInterpreter.ProcessLine('ROOT_VERSION_CODE;') < \
           ROOT.gInterpreter.ProcessLine('ROOT_VERSION(6, 2, 0);'):
            manager.SetMultiThread(True)
        manager.SetMaxThreads(4)

        N = 100000

        rays = ROOT.ARayArray()
        for i in range(N):
            ray = ROOT.ARay(i, wl, 0, 0, 0.8*m, 0, 0, 0, -1)
            rays.Add(ray)

        manager.TraceNonSequential(rays)

        n = rays.GetExited().GetLast() + 1
        ref = (idx - 1)**2/(idx + 1)**2

        self.assertGreater(ref, (n - n**0.5*3)/N)
        self.assertLess(ref, (n + n**0.5*3)/N)

        layer = ROOT.AMultilayer(ROOT.air, ROOT.TiO2)

        angle = ROOT.std.complex(ROOT.double)(45 * deg)
        for wl in (200 * nm, 800 * nm):
            ref, trans = ctypes.c_double(), ctypes.c_double()
            layer.CoherentTMMMixed(angle, wl, ref, trans)

            lens.SetRefractiveIndex(ROOT.TiO2)

            rays = ROOT.ARayArray()
            z, dy, dz = 0.51 * m, 1/2**0.5, -1/2**0.5
            for i in range(N):
                ray = ROOT.ARay(i, wl, 0, 0, z, 0, 0, dy, dz)
                rays.Add(ray)

            manager.SetLimit(3) # stop tracking of photons that entered the lens
            manager.TraceNonSequential(rays)

            n = rays.GetExited().GetLast() + 1
            self.assertGreater(ref.value, (n - n**0.5*3)/N)
            self.assertLess(ref.value, (n + n**0.5*3)/N)

    def testMirrorReflection(self):
        manager = makeTheWorld()

        mirrorbox = ROOT.TGeoBBox("mirrorbox", 0.5*m, 0.5*m, 0.5*m)
        mirror = ROOT.AMirror("mirror", mirrorbox)
        manager.GetTopVolume().AddNode(mirror, 1)
        manager.CloseGeometry()
        if ROOT.gInterpreter.ProcessLine('ROOT_VERSION_CODE;') < \
           ROOT.gInterpreter.ProcessLine('ROOT_VERSION(6, 2, 0);'):
            manager.SetMultiThread(True)
        manager.SetMaxThreads(4)
        
        ROOT.gROOT.ProcessLine('graph = std::make_shared<TGraph>();')
        ROOT.graph.SetPoint(0, 300*nm, 0.)
        ROOT.graph.SetPoint(1, 500*nm, .5) # 0.25 at 400 nm
        mirror.SetReflectance(ROOT.graph)
        self.assertAlmostEqual(mirror.GetReflectance(400*nm, 0), 0.25, 6)

        N = 10000

        rays = ROOT.ARayArray()
        for i in range(N):
            ray = ROOT.ARay(i, 400*nm, 0, 0, 0.8*m, 0, 0, 0, -1)
            rays.Add(ray)

        manager.TraceNonSequential(rays)

        n = rays.GetExited().GetLast() + 1
        ref = 0.25

        self.assertGreater(ref, (n - n**0.5*3)/N)
        self.assertLess(ref, (n + n**0.5*3)/N)
        
        # Test of a 2D reflectance graph
        ROOT.gROOT.ProcessLine('graph2d = std::make_shared<TGraph2D>();')

        # This should be 0.5 at (400 nm, 45 deg)
        ROOT.graph2d.SetPoint(0, 300*nm,  0*deg, 0.0)
        ROOT.graph2d.SetPoint(1, 300*nm, 90*deg, 0.3)
        ROOT.graph2d.SetPoint(2, 500*nm,  0*deg, 0.7)
        ROOT.graph2d.SetPoint(3, 500*nm, 90*deg, 1.0)
        mirror.SetReflectance(ROOT.graph2d)
        self.assertAlmostEqual(mirror.GetReflectance(400*nm, 45*deg), 0.5, 3)

        rays = ROOT.ARayArray()
        for i in range(N):
            x, y, z, t = 0, 0, 0.51*m, 0
            px, py, pz = ROOT.TMath.Sqrt2(), 0, -ROOT.TMath.Sqrt2()
            ray = ROOT.ARay(i, 400*nm, x, y, z, t, px, py, pz)
            rays.Add(ray)

        manager.TraceNonSequential(rays)

        n = rays.GetExited().GetLast() + 1
        ref = 0.5

        self.assertGreater(ref, (n - n**0.5*3)/N)
        self.assertLess(ref, (n + n**0.5*3)/N)

    def testMirrorBoundaryMultilayer(self):
        manager = makeTheWorld()

        mirrorbox = ROOT.TGeoBBox("mirrorbox", 0.5*m, 0.5*m, 0.5*m)
        mirror = ROOT.AMirror("mirror", mirrorbox)

        condition = ROOT.ABorderSurfaceCondition(manager.GetTopVolume(), mirror)
        ROOT.gROOT.ProcessLine('auto mirror_layer = std::make_shared<AMultilayer>(air, Al)');
        ROOT.mirror_layer.InsertLayer(ROOT.SiO2, 25.4 * nm)

        condition.SetMultilayer(ROOT.mirror_layer)

        manager.GetTopVolume().AddNode(mirror, 1)
        manager.CloseGeometry()

        N = 100000

        for wl in range(300, 1100, 100):
            rays = ROOT.ARayArray()
            for i in range(N):
                ray = ROOT.ARay(i, wl * nm, 0, 0, 0.51*m, 0, 1, 0, -1)
                rays.Add(ray)
                manager.TraceNonSequential(rays)

            n_exited = rays.GetExited().GetEntries()
            n_absorbed = rays.GetAbsorbed().GetEntries()
            self.assertEqual(n_exited + n_absorbed, N)

            reflectance = ctypes.c_double()
            transmittance = ctypes.c_double()
            ROOT.mirror_layer.CoherentTMMMixed(ROOT.std.complex(ROOT.double)(45 * deg), wl * nm, reflectance, transmittance)

            expected = N * reflectance.value
            e = expected**0.5
            self.assertGreater(n_exited,  expected - 3*e)
            self.assertLess(n_exited, expected + 3*e)

    def testLensBoundaryMultilayer(self):
        manager = makeTheWorld()

        lensbox = ROOT.TGeoBBox("lensbox", 0.5*m, 0.5*m, 0.5*m)
        lens = ROOT.AMirror("lens", lensbox)

        condition = ROOT.ABorderSurfaceCondition(manager.GetTopVolume(), lens)
        ROOT.gROOT.ProcessLine('auto lens_layer = std::make_shared<AMultilayer>(air, Si)');
        ROOT.lens_layer.InsertLayer(ROOT.SiO2, 2000 * nm)
        ROOT.lens_layer.InsertLayer(ROOT.Si3N4, 33 * nm)

        condition.SetMultilayer(ROOT.lens_layer)

        manager.GetTopVolume().AddNode(lens, 1)
        manager.CloseGeometry()

        N = 100000

        for wl in range(300, 600, 50):
            rays = ROOT.ARayArray()
            for i in range(N):
                ray = ROOT.ARay(i, wl * nm, 0, 0, 0.51*m, 0, 1, 0, -1)
                rays.Add(ray)
                manager.TraceNonSequential(rays)

            n_exited = rays.GetExited().GetEntries()
            n_absorbed = rays.GetAbsorbed().GetEntries()
            self.assertEqual(n_exited + n_absorbed, N)

            reflectance = ctypes.c_double()
            transmittance = ctypes.c_double()
            ROOT.lens_layer.CoherentTMMMixed(ROOT.std.complex(ROOT.double)(45 * deg), wl * nm, reflectance, transmittance)

            expected = N * reflectance.value
            e = expected**0.5
            self.assertGreater(n_exited,  expected - 3*e)
            self.assertLess(n_exited, expected + 3*e)

    def testMirrorScattaring(self):
        manager = makeTheWorld()

        mirrorbox = ROOT.TGeoBBox("mirrorbox", 0.5*m, 0.5*m, 0.5*m)
        mirror = ROOT.AMirror("mirror", mirrorbox)

        condition = ROOT.ABorderSurfaceCondition(manager.GetTopVolume(), mirror)
        sigma = 1
        condition.SetGaussianRoughness(sigma * deg)

        manager.GetTopVolume().AddNode(mirror, 1)
        manager.CloseGeometry()
        if ROOT.gInterpreter.ProcessLine('ROOT_VERSION_CODE;') < \
           ROOT.gInterpreter.ProcessLine('ROOT_VERSION(6, 2, 0);'):
            manager.SetMultiThread(True)
        manager.SetMaxThreads(4)

        N = 10000

        rays = ROOT.ARayArray()
        for i in range(N):
            ray = ROOT.ARay(i, 400*nm, 0, 0, 0.8*m, 0, 0, 0, -1)
            rays.Add(ray)

        manager.TraceNonSequential(rays)

        exited = rays.GetExited()

        h2 = ROOT.TH2D("h2", "h2", 40, -10*sigma, 10*sigma, 40, -10*sigma, 10*sigma)

        for i in range(N):
            ray = exited.At(i)
            p = array.array("d", [0, 0, 0, 0])
            ray.GetDirection(p)
            px = p[0]
            py = p[1]
            pz = p[2]
            h2.Fill(px * rad / deg, py * rad / deg)

        f2 = ROOT.TF2("f2", "[0]*exp(-(x*x + y*y)/(2*[1]*[1]))", -10*sigma, 10*sigma, -10*sigma, 10*sigma)
        f2.SetParameter(0, 1000)
        f2.SetParLimits(1, 0, 10)
        f2.SetParameter(1, sigma)
        h2.Draw("lego")
        ROOT.gPad.Update()
        h2.Fit("f2", "l")
        p = f2.GetParameter(1)
        e = f2.GetParError(1)

        self.assertGreater(2*sigma, p - 3*e) # reflected angle is 2 times larger
        self.assertLess(2*sigma, p + 3*e)

    def testLimitForSuspended(self):
        manager = makeTheWorld()
        manager.SetLimit(1000)

        mirrorsphere = ROOT.TGeoSphere("mirrorsphere", 0.1*m, 0.2*m)
        mirror = ROOT.AMirror("mirror", mirrorsphere)

        manager.GetTopVolume().AddNode(mirror, 1)
        manager.CloseGeometry()
        if ROOT.gInterpreter.ProcessLine('ROOT_VERSION_CODE;') < \
           ROOT.gInterpreter.ProcessLine('ROOT_VERSION(6, 2, 0);'):
            manager.SetMultiThread(True)
        manager.SetMaxThreads(4)

        ray = ROOT.ARay(0, 400*nm, 0, 0, 0, 0, 0, 0, -1)

        manager.TraceNonSequential(ray)

        n = ray.GetNpoints()
        self.assertEqual(n, 1000)

    def testRefractiveIndex(self):
        manager = makeTheWorld()
        lensbox = ROOT.TGeoBBox("lensbox", 0.5*m, 0.5*m, 1*mm)
        lens = ROOT.ALens("lens", lensbox)

        ROOT.gROOT.ProcessLine('graph = std::make_shared<TGraph>();')
        ROOT.graph.SetPoint(0, 400*nm, 1.6)
        ROOT.graph.SetPoint(1, 500*nm, 1.5)
        ROOT.gROOT.ProcessLine('refidx = std::make_shared<ARefractiveIndex>();')
        ROOT.refidx.SetRefractiveIndex(ROOT.graph)
        lens.SetRefractiveIndex(ROOT.refidx)
        n = lens.GetRefractiveIndex(450*nm)
        self.assertEqual(n, 1.55)

    def testSnellsLaw(self):
        manager = makeTheWorld()
        manager.DisableFresnelReflection(True)

        lensbox = ROOT.TGeoBBox("lensbox", 0.5*m, 0.5*m, 1*mm)
        lens = ROOT.ALens("lens", lensbox)

        idx = 1.5
        ROOT.gROOT.ProcessLine('refidx = std::make_shared<ARefractiveIndex>(%.1f);' % idx)
        lens.SetRefractiveIndex(ROOT.refidx)

        manager.GetTopVolume().AddNode(lens, 1)

        focalbox = ROOT.TGeoBBox("focalbox", 0.5*m, 0.5*m, 0.1*mm)
        focal = ROOT.AFocalSurface("focal", focalbox)
        lens.AddNode(focal, 1)

        manager.CloseGeometry()

        theta = 30 * deg
        sint = ROOT.TMath.Sin(theta)
        cost = ROOT.TMath.Cos(theta)
        ray = ROOT.ARay(0, 400*nm, 0*m, 0*m, 2*mm, 0, sint, 0, -cost)
        arr = ROOT.ARayArray()
        #arr.Add(ray)

        ## calling TraceNonSequential(ARay*) causes a seg fault...
        manager.TraceNonSequential(ray)

        p = array.array("d", [0, 0, 0, 0])
        ray.GetDirection(p)
        px = p[0]
        py = p[1]
        pz = p[2]

        self.assertAlmostEqual(px, sint/idx)
        self.assertAlmostEqual(py, 0)

    def testQE(self):
        manager = makeTheWorld()

        focalbox = ROOT.TGeoBBox("focalbox", 0.5*m, 0.5*m, 1*mm)
        focal = ROOT.AFocalSurface("focal", focalbox)

        qe_lambda = ROOT.TGraph()
        qe_lambda.SetPoint(0, 300*nm, 0.0)
        qe_lambda.SetPoint(1, 500*nm, 1.0)

        qe_angle = ROOT.TGraph()
        qe_angle.SetPoint(0,  0 * deg, 1.) # QE = 100% for on-axis photons
        qe_angle.SetPoint(1, 90 * deg, 0.)

        manager.GetTopVolume().AddNode(focal, 1)
        manager.CloseGeometry()
        if ROOT.gInterpreter.ProcessLine('ROOT_VERSION_CODE;') < \
           ROOT.gInterpreter.ProcessLine('ROOT_VERSION(6, 2, 0);'):
            manager.SetMultiThread(True)
        manager.SetMaxThreads(4)

        for i in range(3):
            if i == 1:
                focal.SetQuantumEfficiency(qe_lambda)
            elif i == 2:
                focal.SetQuantumEfficiencyAngle(qe_angle)

            array = ROOT.ARayArray()

            N = 1000**2
            raytr = ROOT.TGeoTranslation("raytr", 0, 0, 2*mm)
            direction = ROOT.TVector3(ROOT.TMath.Cos(45 * deg), 0, -ROOT.TMath.Sin(45 * deg))
            array = ROOT.ARayShooter.Square(400*nm, 1*mm, 1000, 0, raytr, direction)
            manager.TraceNonSequential(array)
        
            nfocused = array.GetFocused().GetLast() + 1
            nstopped = array.GetStopped().GetLast() + 1

            self.assertEqual(nfocused + nstopped, N)
            if i == 0:
                self.assertEqual(nfocused, N)
            elif i == 1:
                p = 0.5
                sigma = (N * (1 - p) * p)**0.5
                self.assertLess(abs(nfocused - N * p), 3*sigma)
            else:
                p = 0.25
                sigma = (N * (1 - p) * p)**0.5
                self.assertLess(abs(nfocused - N * p), 3*sigma)

    def testGlassCatalog(self):
        schott = ROOT.AGlassCatalog('../misc/schottzemax-20180601.agf')
        r = schott.GetRefractiveIndex('N-BK7')
        self.assertAlmostEqual(r.GetRefractiveIndex(589.3 * nm) / 1.51680, 1., 4) # nD
        self.assertAlmostEqual(r.GetExtinctionCoefficient(2325 * nm), 4.2911e-6, 9)

    def testSellmeierFormula(self):
        # N-BK7 from a SCHOTT catalog
        nbk7 = ROOT.ASellmeierFormula(1.03961212, 0.231792344, 1.01046945,
                                      0.00600069867, 0.0200179144, 103.560653)
       
        self.assertAlmostEqual(nbk7.GetRefractiveIndex( 312.6*nm), 1.548620, 4) # n312.6
        self.assertAlmostEqual(nbk7.GetRefractiveIndex( 589.3*nm), 1.516730, 4) # nD
        self.assertAlmostEqual(nbk7.GetRefractiveIndex(1014.0*nm), 1.507310, 4) # nt
        self.assertAlmostEqual(nbk7.GetRefractiveIndex(2325.4*nm), 1.489210, 4) # n2325.4

        self.assertAlmostEqual(nbk7.GetAbbeNumber(), 64.17, 1) # vD, vd = 64.17

        data = ((2325.4*nm, 1.489210),
                (1970.1*nm, 1.494950),
                (1529.6*nm, 1.500910),
                (1060.0*nm, 1.506690),
                (1014.0*nm, 1.507310),
                ( 852.1*nm, 1.509800),
                ( 706.5*nm, 1.512890),
                ( 656.3*nm, 1.514320),
                ( 643.8*nm, 1.514720),
                ( 632.8*nm, 1.515090),
                ( 589.3*nm, 1.516730),
                ( 587.6*nm, 1.516800),
                ( 546.1*nm, 1.518720),
                ( 486.1*nm, 1.522380),
                ( 480.0*nm, 1.522830),
                ( 435.8*nm, 1.526680),
                ( 404.7*nm, 1.530240),
                ( 365.0*nm, 1.536270),
                ( 334.1*nm, 1.542720),
                ( 312.6*nm, 1.548620))

        graph = ROOT.TGraph()
        for i in range(len(data)):
            graph.SetPoint(i, data[i][0], data[i][1])

        nbk7 = ROOT.ASellmeierFormula(1.03961212*0.95, 0.231792344*0.95, 1.01046945*0.95,
                                      0.00600069867*0.95, 0.0200179144*0.95, 103.560653*0.95)

        # These comparisons should fail because B1 to C3 are scaled by 0.95
        self.assertNotAlmostEqual(nbk7.GetRefractiveIndex( 312.6*nm), 1.548620, 3) # n312.6
        self.assertNotAlmostEqual(nbk7.GetRefractiveIndex( 589.3*nm), 1.516730, 3) # nD
        self.assertNotAlmostEqual(nbk7.GetRefractiveIndex(1014.0*nm), 1.507310, 3) # nt
        self.assertNotAlmostEqual(nbk7.GetRefractiveIndex(2325.4*nm), 1.489210, 3) # n2325.4

        f = nbk7.FitData(graph, "N-BK7", "")
        graph.Draw("a*")

        # Will get an almost correct answers. "3" is due to an inperfect fitting result.
        self.assertAlmostEqual(nbk7.GetRefractiveIndex( 312.6*nm), 1.548620, 3) # n312.6
        self.assertAlmostEqual(nbk7.GetRefractiveIndex( 589.3*nm), 1.516730, 3) # nD
        self.assertAlmostEqual(nbk7.GetRefractiveIndex(1014.0*nm), 1.507310, 3) # nt
        self.assertAlmostEqual(nbk7.GetRefractiveIndex(2325.4*nm), 1.489210, 3) # n2325.4

        self.assertAlmostEqual(nbk7.GetRefractiveIndex( 312.6*nm), f.Eval( 312.6*nm), 6) # n312.6
        self.assertAlmostEqual(nbk7.GetRefractiveIndex( 589.3*nm), f.Eval( 589.3*nm), 6) # nD
        self.assertAlmostEqual(nbk7.GetRefractiveIndex(1014.0*nm), f.Eval(1014.0*nm), 6) # nt
        self.assertAlmostEqual(nbk7.GetRefractiveIndex(2325.4*nm), f.Eval(2325.4*nm), 6) # n2325.4

    def testD80(self):
        x0 = 1
        y0 = -1
        r0 = 2
        h2 = ROOT.TH2D('', '', 1000, -3, 3, 1000, -3, 3)
        N = 10000000
        circ = ROOT.gRandom.Circle
        uni = ROOT.gRandom.Uniform
        x, y, r = ctypes.c_double(), ctypes.c_double(), ctypes.c_double()

        for i in range(N):
            circ(x, y, r0)
            scale = uni(0, 1)
            h2.Fill(x.value * scale + x0, y.value * scale + y0)

        ROOT.AGeoUtil.ContainmentRadius(h2, 0.8, r, x, y)
        # 1.5% difference is acceptale
        tor = 0.015
        self.assertLessEqual(abs(x.value / x0 - 1.), tor)
        self.assertLessEqual(abs(y.value / y0 - 1.), tor)
        self.assertLessEqual(abs(r.value / r0 - 0.8)/0.8, tor)

    def testMixedRefractiveIndex(self):
        ROOT.gROOT.ProcessLine('std::shared_ptr<ARefractiveIndex> medA(new ARefractiveIndex(1., 1.));')
        ROOT.gROOT.ProcessLine('std::shared_ptr<ARefractiveIndex> medB(new ARefractiveIndex(2., 2.));')
        mixed = ROOT.AMixedRefractiveIndex(ROOT.medA, ROOT.medB, 3, 7)
        nA = ROOT.medA.GetRefractiveIndex(100 * nm)
        nB = ROOT.medB.GetRefractiveIndex(100 * nm)
        kA = ROOT.medA.GetExtinctionCoefficient(100 * nm)
        kB = ROOT.medB.GetExtinctionCoefficient(100 * nm)

        n = mixed.GetRefractiveIndex(100 * nm)
        k = mixed.GetExtinctionCoefficient(100 * nm)

        self.assertAlmostEqual(n, nA * 0.3 + nB * 0.7)
        self.assertAlmostEqual(k, kA * 0.3 + kB * 0.7)

    def testTMM(self):
        # Copied from tmm.tests.basic_test()
        ROOT.gROOT.ProcessLine('std::shared_ptr<ARefractiveIndex> med1(new ARefractiveIndex(1.));')
        ROOT.gROOT.ProcessLine('std::shared_ptr<ARefractiveIndex> med2(new ARefractiveIndex(2., 4.));')
        ROOT.gROOT.ProcessLine('std::shared_ptr<ARefractiveIndex> med3(new ARefractiveIndex(3., .3));')
        ROOT.gROOT.ProcessLine('std::shared_ptr<ARefractiveIndex> med4(new ARefractiveIndex(1., .1));')

        multi = ROOT.AMultilayer(ROOT.med1, ROOT.med4)
        multi.InsertLayer(ROOT.med2, 2)
        multi.InsertLayer(ROOT.med3, 3)
        th_0 = ROOT.std.complex(ROOT.double)(0.1)
        lam_vac = 100 # Units are not important

        rs, rp = 0.37273208839139516, 0.37016110373044969
        ts, tp = 0.22604491247079261, 0.22824374314132009

        reflectance = ctypes.c_double()
        transmittance = ctypes.c_double()
        multi.CoherentTMM(ROOT.AMultilayer.kS, th_0, lam_vac, reflectance, transmittance)
        self.assertAlmostEqual(reflectance.value, rs)
        self.assertAlmostEqual(transmittance.value, ts)

        multi.CoherentTMM(ROOT.AMultilayer.kP, th_0, lam_vac, reflectance, transmittance)
        self.assertAlmostEqual(reflectance.value, rp)
        self.assertAlmostEqual(transmittance.value, tp)

        multi.CoherentTMMMixed(th_0, lam_vac, reflectance, transmittance)
        self.assertAlmostEqual(reflectance.value, (rs + rp) / 2.)
        self.assertAlmostEqual(transmittance.value, (ts + tp) / 2.)

        wavelength_v = ROOT.vector('Double_t')()
        answer = []

        for i in range(300, 800):
            wavelength_v.push_back(i)
            multi.CoherentTMMMixed(th_0, wavelength_v.back(), reflectance, transmittance)
            answer.append((reflectance.value, transmittance.value))

        reflectance_v = ROOT.vector('Double_t')()
        transmittance_v = ROOT.vector('Double_t')()
        multi.CoherentTMMMixed(th_0, wavelength_v, reflectance_v, transmittance_v)

        for i in range(wavelength_v.size()):
            self.assertAlmostEqual(answer[i][0], reflectance_v[i])
            self.assertAlmostEqual(answer[i][1], transmittance_v[i])

        angle_v = ROOT.vector('std::complex<Double_t>')()
        answer = []

        for i in range(500):
            angle_v.push_back(ROOT.std.complex(ROOT.double)(i * ROOT.TMath.Pi() / 2000.))
            multi.CoherentTMMMixed(angle_v.back(), lam_vac, reflectance, transmittance)
            answer.append((reflectance.value, transmittance.value))
            
        multi.CoherentTMMMixed(angle_v, lam_vac, reflectance_v, transmittance_v)

        for i in range(angle_v.size()):
            self.assertAlmostEqual(answer[i][0], reflectance_v[i])
            self.assertAlmostEqual(answer[i][1], transmittance_v[i])

if __name__=="__main__":
    ROOT.gRandom.SetSeed(int(time.time()))
    suite = unittest.TestLoader().loadTestsFromTestCase(TestROBAST)
    unittest.TextTestRunner(verbosity=2).run(suite)
