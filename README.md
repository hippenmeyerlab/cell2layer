# cell2layer
---
Cell2layer quantifies relative and absolute positions of manually marked cells within
manually defined layers.

### Input
First, cell layers are defined by `Segmented Line` ROIS in
ImageJ and added to the `ROI Manager`. Each layer ROI marks the boundary of the
subsequent layers. Then, points (usually cell positions) are marked with ImageJ's `Point` ROI, and are also added to the manager. The naming of the ROIs can be arbritary, but layer boundariy ROIs need to be added in sequential order.


<img src="img/layers_and_points_definition.png" alt="Mannually add layer borders and points of interest" width="512"/>

### Output
Executing the `cell2layer.py` Fiji (jython) script, will assign each marked point to
the layer (marked in magenta) where it is placed in. Cells marked outside of the layer boundaries's convex hull are discarded.

<img src="img/cell_layer_assignment.png" alt="Points are assigned to layers as defined by the layer borders" width="512"/>

The script computes the relative and absolute positions of each marked point regarding
the first and last layer boundaries, as well as, its relative position within its assigned layer. For each marked point the *shortest distance* to the first (`cell_abs_distance_to_first_layer`) and last layer (`cell_abs_distance_to_last_layer`) boundary is computed (in pixel). From this, the relative position (`cell_relative_dist`) of the point is derived, where the first layer boundary is defined as 0 and the last as 1.

To extract relative position of a marked point within its assinged layer, the same computation is applied for the layer boundaries of the layer, where the point was assined to. (`cell_relative_intra_dist`).

Furthermore, the relative size of each layer is approximated as ratios of the layer sizes according to the perpendicular central axis connecting the the centers of each layer boundary. Additonally, the signal intensity of each input channel of the image is extracted and added to the output table.

## Result
The following tab separated table is written as output.

<img src="img/result_table.png" alt="Points are assigned to layers as defined by the layer borders" style="width:95%;"/>
