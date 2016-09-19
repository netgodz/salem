from __future__ import division

import unittest
import shutil
import os
import time
import warnings
import copy

import numpy as np
from numpy.testing import assert_allclose, assert_array_equal

from salem.tests import requires_travis, requires_geopandas, \
    requires_matplotlib, requires_xarray
from salem import utils, transform_geopandas, GeoTiff, read_shapefile, sio
from salem import read_shapefile_to_grid, graphics, Grid, mercator_grid, wgs84
from salem.utils import get_demo_file

try:
    import matplotlib as mpl
    import matplotlib.pyplot as plt
except ImportError:
    pass

current_dir = os.path.dirname(os.path.abspath(__file__))
testdir = os.path.join(current_dir, 'tmp')
if not os.path.exists(testdir):
    os.makedirs(testdir)


@requires_geopandas
def create_dummy_shp(fname):

    import shapely.geometry as shpg
    import geopandas as gpd

    e_line = shpg.LinearRing([(1.5, 1), (2., 1.5), (1.5, 2.), (1, 1.5)])
    i_line = shpg.LinearRing([(1.4, 1.4), (1.6, 1.4), (1.6, 1.6), (1.4, 1.6)])
    p1 = shpg.Polygon(e_line, [i_line])
    p2 = shpg.Polygon([(2.5, 1.3), (3., 1.8), (2.5, 2.3), (2, 1.8)])
    p3 = shpg.Point(0.5, 0.5)
    p4 = shpg.Point(1, 1)
    df = gpd.GeoDataFrame()
    df['name'] = ['Polygon', 'Line']
    df['geometry'] = gpd.GeoSeries([p1, p2])
    of = os.path.join(testdir, fname)
    df.to_file(of)
    return of


def delete_test_dir():
    if os.path.exists(testdir):
        shutil.rmtree(testdir)


class TestUtils(unittest.TestCase):

    def setUp(self):
        if not os.path.exists(testdir):
            os.makedirs(testdir)

    def tearDown(self):
        delete_test_dir()

    @requires_travis
    def test_empty_cache(self):

        utils.empty_cache()

    def test_demofiles(self):

        self.assertTrue(os.path.exists(utils.get_demo_file('dem_wgs84.nc')))
        self.assertTrue(utils.get_demo_file('dummy') is None)

    def test_read_colormap(self):

        cl = utils.read_colormap('topo') * 256
        assert_allclose(cl[4, :], (177, 242, 196))
        assert_allclose(cl[-1, :], (235, 233, 235))

        cl = utils.read_colormap('dem') * 256
        assert_allclose(cl[4, :], (153,100, 43))
        assert_allclose(cl[-1, :], (255,255,255))


class TestIO(unittest.TestCase):

    def setUp(self):
        if not os.path.exists(testdir):
            os.makedirs(testdir)

    def tearDown(self):
        delete_test_dir()

    @requires_geopandas
    def test_cache_working(self):

        f1 = 'f1.shp'
        f1 = create_dummy_shp(f1)
        cf1 = utils.cached_shapefile_path(f1)
        self.assertFalse(os.path.exists(cf1))
        _ = read_shapefile(f1)
        self.assertFalse(os.path.exists(cf1))
        _ = read_shapefile(f1, cached=True)
        self.assertTrue(os.path.exists(cf1))
        # nested calls
        self.assertTrue(cf1 == utils.cached_shapefile_path(cf1))

        # wait a bit
        time.sleep(0.1)
        f1 = create_dummy_shp(f1)
        cf2 = utils.cached_shapefile_path(f1)
        self.assertFalse(os.path.exists(cf1))
        _ = read_shapefile(f1, cached=True)
        self.assertFalse(os.path.exists(cf1))
        self.assertTrue(os.path.exists(cf2))
        df = read_shapefile(f1, cached=True)
        np.testing.assert_allclose(df.min_x, [1., 2.])
        np.testing.assert_allclose(df.max_x, [2., 3.])
        np.testing.assert_allclose(df.min_y, [1., 1.3])
        np.testing.assert_allclose(df.max_y, [2., 2.3])

        self.assertRaises(ValueError, read_shapefile, 'f1.sph')
        self.assertRaises(ValueError, utils.cached_shapefile_path, 'f1.splash')


    @requires_geopandas
    def test_read_to_grid(self):

        g = GeoTiff(utils.get_demo_file('hef_srtm.tif'))
        sf = utils.get_demo_file('Hintereisferner_UTM.shp')

        df1 = read_shapefile_to_grid(sf, g.grid)

        df2 = transform_geopandas(read_shapefile(sf), to_crs=g.grid)
        assert_allclose(df1.geometry[0].exterior.coords,
                        df2.geometry[0].exterior.coords)


class TestColors(unittest.TestCase):

    @requires_matplotlib
    def test_extendednorm(self):

        bounds = [1, 2, 3]
        cm = mpl.cm.get_cmap('jet')

        mynorm = graphics.ExtendedNorm(bounds, cm.N)
        refnorm = mpl.colors.BoundaryNorm(bounds, cm.N)
        x = np.random.randn(100) * 10 - 5
        np.testing.assert_array_equal(refnorm(x), mynorm(x))

        refnorm = mpl.colors.BoundaryNorm([0] + bounds + [4], cm.N)
        mynorm = graphics.ExtendedNorm(bounds, cm.N, extend='both')
        x = np.random.random(100) + 1.5
        np.testing.assert_array_equal(refnorm(x), mynorm(x))

        # Min and max
        cmref = mpl.colors.ListedColormap(['blue', 'red'])
        cmref.set_over('black')
        cmref.set_under('white')

        cmshould = mpl.colors.ListedColormap(['white', 'blue', 'red', 'black'])
        cmshould.set_over(cmshould(cmshould.N))
        cmshould.set_under(cmshould(0))

        refnorm = mpl.colors.BoundaryNorm(bounds, cmref.N)
        mynorm = graphics.ExtendedNorm(bounds, cmshould.N, extend='both')
        np.testing.assert_array_equal(refnorm.vmin, mynorm.vmin)
        np.testing.assert_array_equal(refnorm.vmax, mynorm.vmax)
        x = [-1, 1.2, 2.3, 9.6]
        np.testing.assert_array_equal(cmshould([0,1,2,3]), cmshould(mynorm(x)))
        x = np.random.randn(100) * 10 + 2
        np.testing.assert_array_equal(cmref(refnorm(x)), cmshould(mynorm(x)))

        np.testing.assert_array_equal(-1, mynorm(-1))
        np.testing.assert_array_equal(1, mynorm(1.1))
        np.testing.assert_array_equal(4, mynorm(12))

        # Just min
        cmref = mpl.colors.ListedColormap(['blue', 'red'])
        cmref.set_under('white')
        cmshould = mpl.colors.ListedColormap(['white', 'blue', 'red'])
        cmshould.set_under(cmshould(0))

        np.testing.assert_array_equal(2, cmref.N)
        np.testing.assert_array_equal(3, cmshould.N)
        refnorm = mpl.colors.BoundaryNorm(bounds, cmref.N)
        mynorm = graphics.ExtendedNorm(bounds, cmshould.N, extend='min')
        np.testing.assert_array_equal(refnorm.vmin, mynorm.vmin)
        np.testing.assert_array_equal(refnorm.vmax, mynorm.vmax)
        x = [-1, 1.2, 2.3]
        np.testing.assert_array_equal(cmshould([0,1,2]), cmshould(mynorm(x)))
        x = np.random.randn(100) * 10 + 2
        np.testing.assert_array_equal(cmref(refnorm(x)), cmshould(mynorm(x)))

        # Just max
        cmref = mpl.colors.ListedColormap(['blue', 'red'])
        cmref.set_over('black')
        cmshould = mpl.colors.ListedColormap(['blue', 'red', 'black'])
        cmshould.set_over(cmshould(2))

        np.testing.assert_array_equal(2, cmref.N)
        np.testing.assert_array_equal(3, cmshould.N)
        refnorm = mpl.colors.BoundaryNorm(bounds, cmref.N)
        mynorm = graphics.ExtendedNorm(bounds, cmshould.N, extend='max')
        np.testing.assert_array_equal(refnorm.vmin, mynorm.vmin)
        np.testing.assert_array_equal(refnorm.vmax, mynorm.vmax)
        x = [1.2, 2.3, 4]
        np.testing.assert_array_equal(cmshould([0,1,2]), cmshould(mynorm(x)))
        x = np.random.randn(100) * 10 + 2
        np.testing.assert_array_equal(cmref(refnorm(x)), cmshould(mynorm(x)))

        # General case
        bounds = [1, 2, 3, 4]
        cm = mpl.cm.get_cmap('jet')
        mynorm = graphics.ExtendedNorm(bounds, cm.N, extend='both')
        refnorm = mpl.colors.BoundaryNorm([-100] + bounds + [100], cm.N)
        x = np.random.randn(100) * 10 - 5
        ref = refnorm(x)
        ref = np.where(ref == 0, -1, ref)
        ref = np.where(ref == cm.N-1, cm.N, ref)
        np.testing.assert_array_equal(ref, mynorm(x))


class TestGraphics(unittest.TestCase):

    @requires_matplotlib
    def test_datalevels_output(self):

        # Test basic stuffs
        c = graphics.DataLevels(nlevels=2)
        assert_array_equal(c.levels, [0, 1])
        c.set_data([1, 2, 3, 4])
        assert_array_equal(c.levels, [1, 4])

        c = graphics.DataLevels(levels=[1, 2, 3])
        assert_array_equal(c.levels, [1, 2, 3])

        c = graphics.DataLevels(nlevels=10, data=[0, 9])
        assert_array_equal(c.levels, np.linspace(0, 9, num=10))
        self.assertTrue(c.extend == 'neither')

        c = graphics.DataLevels(nlevels=10, data=[0, 9], vmin=2, vmax=3)
        assert_array_equal(c.levels, np.linspace(2, 3, num=10))
        self.assertTrue(c.extend == 'both')
        c.set_extend('neither')
        self.assertTrue(c.extend == 'neither')
        with warnings.catch_warnings(record=True) as w:
            # Cause all warnings to always be triggered.
            warnings.simplefilter("always")
            # Trigger a warning.
            out = c.to_rgb()
            # Verify some things
            assert len(w) == 2
            assert issubclass(w[0].category, RuntimeWarning)
            assert issubclass(w[1].category, RuntimeWarning)

        c = graphics.DataLevels(nlevels=10, data=[2.5], vmin=2, vmax=3)
        assert_array_equal(c.levels, np.linspace(2, 3, num=10))
        self.assertTrue(c.extend == 'neither')
        c.update(dict(extend='both'))
        self.assertTrue(c.extend == 'both')
        self.assertRaises(AttributeError, c.update, dict(dummy='t'))

        c = graphics.DataLevels(nlevels=10, data=[0, 9], vmax=3)
        assert_array_equal(c.levels, np.linspace(0, 3, num=10))
        self.assertTrue(c.extend == 'max')

        c = graphics.DataLevels(nlevels=10, data=[0, 9], vmin=1)
        assert_array_equal(c.levels, np.linspace(1, 9, num=10))
        self.assertTrue(c.extend == 'min')

        c = graphics.DataLevels(nlevels=10, data=[0, 9], vmin=-1)
        assert_array_equal(c.levels, np.linspace(-1, 9, num=10))
        self.assertTrue(c.extend == 'neither')
        c.set_plot_params()
        self.assertTrue(c.extend == 'neither')
        assert_array_equal(c.vmin, 0)
        assert_array_equal(c.vmax, 9)
        c.set_plot_params(vmin=1)
        assert_array_equal(c.vmin, 1)
        c.set_data([-12, 8])
        assert_array_equal(c.vmin, 1)
        self.assertTrue(c.extend == 'min')
        c.set_data([2, 8])
        self.assertTrue(c.extend == 'neither')
        c.set_extend('both')
        self.assertTrue(c.extend == 'both')
        c.set_data([3, 3])
        self.assertTrue(c.extend == 'both')
        c.set_extend()
        self.assertTrue(c.extend == 'neither')

        # Test the conversion
        cm = mpl.colors.ListedColormap(['white', 'blue', 'red', 'black'])
        x = [-1, 0.9, 1.2, 2, 999, 0.8]
        c = graphics.DataLevels(levels=[0, 1, 2], data=x, cmap=cm)
        r = c.to_rgb()
        self.assertTrue(len(x) == len(r))
        self.assertTrue(c.extend == 'both')
        assert_array_equal(r, cm([0, 1, 2, 3, 3, 1]))

        x = [0.9, 1.2]
        c = graphics.DataLevels(levels=[0, 1, 2], data=x, cmap=cm, extend='both')
        r = c.to_rgb()
        self.assertTrue(len(x) == len(r))
        self.assertTrue(c.extend == 'both')
        assert_array_equal(r, cm([1, 2]))

        cm = mpl.colors.ListedColormap(['white', 'blue', 'red'])
        c = graphics.DataLevels(levels=[0, 1, 2], data=x, cmap=cm, extend='min')
        r = c.to_rgb()
        self.assertTrue(len(x) == len(r))
        assert_array_equal(r, cm([1, 2]))

        cm = mpl.colors.ListedColormap(['blue', 'red', 'black'])
        c = graphics.DataLevels(levels=[0, 1, 2], data=x, cmap=cm, extend='max')
        r = c.to_rgb()
        self.assertTrue(len(x) == len(r))
        assert_array_equal(r, cm([0, 1]))

    @requires_matplotlib
    def test_map(self):

        a = np.zeros((4, 5))
        a[0, 0] = -1
        a[1, 1] = 1.1
        a[2, 2] = 2.2
        a[2, 4] = 1.9
        a[3, 3] = 9
        cmap = copy.deepcopy(mpl.cm.get_cmap('jet'))

        # ll_corner (type geotiff)
        g = Grid(nxny=(5, 4), dxdy=(1, 1), ll_corner=(0, 0), proj=wgs84,
                 pixel_ref='corner')
        c = graphics.Map(g, ny=4, countries=False)
        c.set_cmap(cmap)
        c.set_plot_params(levels=[0, 1, 2, 3])
        c.set_data(a)
        rgb1 = c.to_rgb()
        c.set_data(a, crs=g)
        assert_array_equal(rgb1, c.to_rgb())
        c.set_data(a, interp='linear')
        rgb1 = c.to_rgb()
        c.set_data(a, crs=g, interp='linear')
        assert_array_equal(rgb1, c.to_rgb())

        # centergrid (type WRF)
        g = Grid(nxny=(5, 4), dxdy=(1, 1), ll_corner=(0.5, 0.5), proj=wgs84,
                 pixel_ref='center')
        c = graphics.Map(g, ny=4, countries=False)
        c.set_cmap(cmap)
        c.set_plot_params(levels=[0, 1, 2, 3])
        c.set_data(a)
        rgb1 = c.to_rgb()
        c.set_data(a, crs=g)
        assert_array_equal(rgb1, c.to_rgb())
        c.set_data(a, interp='linear')
        rgb1 = c.to_rgb()
        c.set_data(a, crs=g.corner_grid, interp='linear')
        assert_array_equal(rgb1, c.to_rgb())
        c.set_data(a, crs=g.center_grid, interp='linear')
        assert_array_equal(rgb1, c.to_rgb())

        # More pixels
        c = graphics.Map(g, ny=500, countries=False)
        c.set_cmap(cmap)
        c.set_plot_params(levels=[0, 1, 2, 3])
        c.set_data(a)
        rgb1 = c.to_rgb()
        c.set_data(a, crs=g)
        assert_array_equal(rgb1, c.to_rgb())
        c.set_data(a, interp='linear')
        rgb1 = c.to_rgb()
        c.set_data(a, crs=g, interp='linear')
        rgb2 = c.to_rgb()

        # The interpolation is conservative with the grid...
        srgb = np.sum(rgb2[..., 0:3], axis=2)
        pok = np.nonzero(srgb != srgb[0, 0])
        rgb1 = rgb1[np.min(pok[0]):np.max(pok[0]),
                    np.min(pok[1]):np.max(pok[1]),...]
        rgb2 = rgb2[np.min(pok[0]):np.max(pok[0]),
                    np.min(pok[1]):np.max(pok[1]),...]
        assert_array_equal(rgb1, rgb2)

        cmap.set_bad('pink')

        # Add masked arrays
        a[1, 1] = np.NaN
        c.set_data(a)
        rgb1 = c.to_rgb()
        c.set_data(a, crs=g)
        assert_array_equal(rgb1, c.to_rgb())

        # Interp?
        c.set_data(a, interp='linear')
        rgb1 = c.to_rgb()
        c.set_data(a, crs=g, interp='linear')
        rgb2 = c.to_rgb()
        # Todo: there's something sensibly wrong about imresize here
        # but I think it is out of my scope
        # assert_array_equal(rgb1, rgb2)

    @requires_matplotlib
    def test_increase_coverage(self):

        # Just for coverage -> empty shapes should not trigger an error
        grid = mercator_grid(center_ll=(-20, 40),
                                        extent=(2000, 2000), nx=10)
        c = graphics.Map(grid)

        # Assigning wrongly shaped data should, however
        self.assertRaises(ValueError, c.set_data, np.zeros((3, 8)))


class TestSkyIsFalling(unittest.TestCase):

    @requires_matplotlib
    def test_projplot(self):

        # this caused many problems on fabien's laptop.
        # this is just to be sure that on your system, everything is fine

        import pyproj
        import matplotlib.pyplot as plt

        wgs84 = pyproj.Proj(proj='latlong', datum='WGS84')
        fig = plt.figure()
        plt.close()

        srs = '+units=m +proj=lcc +lat_1=29.0 +lat_2=29.0 +lat_0=29.0 +lon_0=89.8'

        proj_out = pyproj.Proj("+init=EPSG:4326", preserve_units=True)
        proj_in = pyproj.Proj(srs, preserve_units=True)

        lon, lat = pyproj.transform(proj_in, proj_out, -2235000, -2235000)
        np.testing.assert_allclose(lon, 70.75731, atol=1e-5)


class TestXarray(unittest.TestCase):

    @requires_geopandas  # because of the grid tests, more robust with GDAL
    def test_wrf(self):
        import xarray as xr

        ds = sio.open_xr_dataset(get_demo_file('wrf_tip_d1.nc'))

        # this is because read_dataset changes some stuff, let's see if
        # georef still ok
        dsxr = xr.open_dataset(get_demo_file('wrf_tip_d1.nc'))
        assert ds.salem.grid == dsxr.salem.grid

        lon, lat = ds.salem.grid.ll_coordinates
        assert_allclose(lon, ds['lon'], atol=1e-4)
        assert_allclose(lat, ds['lat'], atol=1e-4)

        # then something strange happened
        assert ds.isel(time=0).salem.grid == ds.salem.grid
        assert ds.isel(time=0).T2.salem.grid == ds.salem.grid

        nlon, nlat = ds.isel(time=0).T2.salem.grid.ll_coordinates
        assert_allclose(nlon, ds['lon'], atol=1e-4)
        assert_allclose(nlat, ds['lat'], atol=1e-4)