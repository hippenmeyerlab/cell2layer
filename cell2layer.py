import os
import sys
import csv
import math
import jarray
from ij import IJ, ImagePlus
from java.awt import Color, Font
from ij.io import DirectoryChooser
from ij.plugin.frame import RoiManager
from ij.gui import Roi, Overlay, PolygonRoi, PointRoi, TextRoi, Line, ShapeRoi

from ij.plugin.Selection import lineToArea


def get_distances(border, points, imp):
	# http://csharphelper.com/blog/2016/09/find-the-shortest-distance-between-a-point-and-a-line-segment-in-c/
	distances = []
	for p in points:
		x0 = int(p.getX())
		y0 = int(p.getY())

		border_poly = border.getFloatPolygon()

		tmp_dist = []
		for i in range(border_poly.npoints-1):
			x1 = border_poly.xpoints[i]
			x2 = border_poly.xpoints[i+1]
			y1 = border_poly.ypoints[i]
			y2 = border_poly.ypoints[i+1]

			dy = y2 - y1
			dx = x2 - x1

			t = ((x0 - x1) * dx + (y0 - y1) * dy) / (dx * dx + dy * dy)
			if t < 0:
				# 1st point closest
				dist_x = x0 - x1
				dist_y = y0 - y1
			elif t > 1:
				# second point closest
				dist_x = x0 - x2
				dist_y = y0 - y2
			else:
				# closest point on the line segment
				dist_x = x0 - (x1 + t * dx)
				dist_y = y0 - (y1 + t * dy)

			dist = math.sqrt(dist_x**2 + dist_y**2)
			tmp_dist.append(dist)

		distances.append(min(tmp_dist))

	return distances


def get_point_counter(points):
	return [points.getCounter(i) for i, _ in enumerate(points)]

def construct_layer(pl1, pl2):
	layer_poly = pl1.clone()
	layer_poly = layer_poly.getFloatPolygon()

	x0 = pl1.getFloatPolygon().xpoints[0]
	y0 = pl1.getFloatPolygon().ypoints[0]

	x1 = pl2.getFloatPolygon().xpoints[0]
	y1 = pl2.getFloatPolygon().ypoints[0]

	x2 = pl2.getFloatPolygon().xpoints[-1]
	y2 = pl2.getFloatPolygon().ypoints[-1]

	d1 = (x0-x1)*(x0-x1) + (y0-y1)*(y0-y1)
	d2 = (x0-x2)*(x0-x2) + (y0-y2)*(y0-y2)

	if d2 <= d1:
		for (x,y) in zip(pl2.getFloatPolygon().xpoints, pl2.getFloatPolygon().ypoints):
			layer_poly.addPoint(x, y)
	else:
		# reverse adding
		for (x,y) in zip(pl2.getFloatPolygon().xpoints, pl2.getFloatPolygon().ypoints)[::-1]:
			layer_poly.addPoint(x, y)

	return PolygonRoi(layer_poly, Roi.POLYGON)

def get_layers_polygons(ordered_layers):
	res = []
	for bly1, bly2 in zip(ordered_layers, ordered_layers[1:]):
		res.append(construct_layer(bly1, bly2))
	return res


def in_layer(points, layers):
	res = []
	for p in points:
		layer_assignment = filter(lambda xxx: xxx[1].contains(int(p.getX()), int(p.getY())), enumerate(layers))
		if len(layer_assignment) == 0:
			res.append(-1)
		else:
			res.append(layer_assignment[0][0])
	return res

def get_signal(imp, points):
	signals = {}
	if imp.getType() == ImagePlus.COLOR_RGB:
		# RGB
		signals["red"]   = []
		signals["green"] = []
		signals["blue"]  = []
		for p in points:
			rgb = jarray.zeros(3, "i")
			imp.getProcessor().getPixel(int(p.getX()), int(p.getY()), rgb)
			signals["red"]  .append(rgb[0])
			signals["green"].append(rgb[1])
			signals["blue"] .append(rgb[2])
	else:
		nc = imp.getNChannels()
		for c in range(nc):
			signals["ch{:02}".format(c)] = []
		for c in range(nc):
			# API method "imp.getProcessor(c+1)" does not work as excpected
			# Solution: http://forum.imagej.net/t/compositeimage-object-creation-results-in-missing-imageprocessor/545/4
			cProcessor = imp.getStack().getProcessor(c+1)
			for p in points:
				value = cProcessor.getPixel(int(p.getX()), int(p.getY()))
				signals["ch{:02}".format(c)]  .append(value)

	return signals

def get_layer_dist_lkp(layers, imp):
	xp0 = layers[0].getInterpolatedPolygon().xpoints
	yp0 = layers[0].getInterpolatedPolygon().ypoints
	mid = int(len(xp0) / 2)
	xp0 = xp0[mid]
	yp0 = yp0[mid]

	xp1 = layers[-1].getInterpolatedPolygon().xpoints
	yp1 = layers[-1].getInterpolatedPolygon().ypoints
	mid = int(len(xp1) / 2)
	xp1 = xp1[mid]
	yp1 = yp1[mid]

	perp_line = lineToArea(Line(xp0, yp0, xp1, yp1))

	layer_dist_lkp = []
	for l in layers[1:-1]:
		lcopy = l.clone()
		lcopy.setStrokeWidth(1)
		intersect = ShapeRoi(perp_line.clone()).and(ShapeRoi(lineToArea(ShapeRoi(lcopy))))
		xi = intersect.getFloatPolygon().xpoints[0]
		yi = intersect.getFloatPolygon().ypoints[0]
		d1 =  get_distances(layers[0], PointRoi(xi, yi), imp)[0]
		d2 =  get_distances(layers[-1], PointRoi(xi, yi), imp)[0]
		layer_dist_lkp.append(d1 / (d1+d2))

	layer_dist_lkp = [0] + layer_dist_lkp + [1]
	return layer_dist_lkp, perp_line

def get_out_dir(imp):
	f_info = imp.getOriginalFileInfo()
	if not f_info:
		dc = DirectoryChooser("Choose directory to save results")
		outDir = dc.getDirectory()
	else:
		outDir = f_info.directory
	return outDir


def export_to_csv(p_x, p_y, p_type, p_layer, p_rel_dist,  p_rel_intra_dist, p_distances, p_signals, layer_dist_lkp, imp):
	out_dir = get_out_dir(imp)

	#print len(p_x), len(p_y), len(p_type), len(p_layer), len(p_rel_dist), len(p_rel_intra_dist), len(p_distances), len(p_signals), len(layer_dist_lkp)
	with open(os.path.join(out_dir, imp.getShortTitle() + "_results.txt"), 'wb') as csv_file:
		csv_writer = csv.writer(csv_file, delimiter='\t')
		csv_writer.writerow(["id", "x_pos", "y_pos", "cell_type", "cell_in_layer",
							 "cell_relative_dist", "cell_relative_intra_dist",
							 "cell_abs_distance_to_first_layer", "cell_abs_distance_to_last_layer",
							 "layer_rel_distance_of_cells_layer"] + map(lambda xxx: "signal_"+xxx, p_signals.keys()))

		for row, (x, y, t, l, d) in enumerate(zip(p_x, p_y, p_type, p_layer, p_rel_dist)):
			if l < 0:
				# write error
				res = [row, x, y, "point outside convex hull of layers"]
				csv_writer.writerow(res)
				continue

			dist_rel_to_layer = p_rel_intra_dist[l][row]

			dist_to_outer_layer_1 = p_distances[0][row]
			dist_to_outer_layer_2 = p_distances[-1][row]

			dist_of_layer = layer_dist_lkp[l]

			signal_list = []
			for sr in p_signals.values():
				signal_list.append(sr[row])

			res = [row, x, y, t, l, d, dist_rel_to_layer, dist_to_outer_layer_1, dist_to_outer_layer_2, dist_of_layer] + signal_list

			csv_writer.writerow(res)

def save_rois(rm, imp):
	out_dir = get_out_dir(imp)
	rm.runCommand("Deselect"); # deselect ROIs to save them all
	rm.runCommand("Save", os.path.join(out_dir, imp.getShortTitle() + "_rois.zip"));


def main():
	rm = RoiManager.getInstance()
	imp = IJ.getImage()

	rois = list(rm.getRoisAsArray())

	layers = filter(lambda xxx: xxx.__class__ == PolygonRoi, rois)
	if len(layers) < 2:
		IJ.showMessage("Please mark at least two layers")

	points = filter(lambda xxx: xxx.__class__ == PointRoi, rois)
	if len(points) != 1:
		IJ.showMessage("Please mark at exactly one point cloud")

	points = points[0]

	layer_dist_lkp, perp_line = get_layer_dist_lkp(layers, imp)


	p_distances = []
	for l in layers:
		p_distances.append(get_distances(l, points, imp))


	p_rel_dist   = [d1 / (d1+d2) for d1, d2 in zip(p_distances[0], p_distances[-1])]

	p_rel_intra_dist = []
	if len(layers) >= 2:
		for k in range(len(p_distances)-1):
			p_rel_intra_dist.append([d1 / (d1+d2) for d1, d2 in zip(p_distances[k], p_distances[k+1])])


	p_type = get_point_counter(points)

	p_x = map(lambda xxx: int(xxx.getX()), points)
	p_y = map(lambda xxx: int(xxx.getY()), points)

	layers_poly = get_layers_polygons(layers)
	p_layer = in_layer(points, layers_poly)


	p_signals = get_signal(imp, points)


	#########################################################
	try:
		export_to_csv(p_x, p_y, p_type, p_layer, p_rel_dist,  p_rel_intra_dist, p_distances, p_signals, layer_dist_lkp, imp)
	except IOError as e:
		IJ.showMessage("Cannot write result file. File is locked or opened with another program.\n{}".format(imp.getShortTitle()))
		return


	save_rois(rm, imp)

	IJ.showMessage("Results written to '{}_results.txt'".format(imp.getShortTitle()))

	font = Font("Arial", Font.PLAIN, 16);
	overlay = Overlay()

	for lp in layers_poly:
		lp.setStrokeColor(Color.white)
		overlay.add(lp)

	overlay.add(points)
	overlay.add(perp_line)

	for k, (x, y, t, l, d) in enumerate(zip(p_x, p_y, p_type, p_layer, p_rel_dist)):
		tr = TextRoi("id{}; {:0.2f}; L{}".format(k, p_rel_dist[k], l), x,y, font)
		col = Color.red if t == 0 else Color.green
		tr.setStrokeColor(col)
		tr.setNonScalable(True)
		overlay.add(tr)
	imp.setOverlay(overlay)

	imp.updateAndDraw()
	imp.show()

if __name__ in ["__main__", "__builtin__"]:
    main()
