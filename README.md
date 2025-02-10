&emsp;
<p align="center">
<img width="70%" height="70%" src="SphereDetect.png">
</p>

# SphereDetect
Imaging spheroids in high-content assays can lead to collecting a lot of empty data. Especially finding a spheroids starting point can be challenging. There are ways to do it, but most of them are proprietary and specific to the microscope system. We used this to detect spheroids imaged in a 384-well plate<sup>[1](#Ref2025)</sup>.

Here we present SphereDetect, which implements an algorithm to automatically detect the first spheroid section in a Z-stack. The algorithm relies on a spheroid coming into focus as one starts imaging in Z. Specifically, it finds the maximum change in FocusScore <sup>[2](#RefFocusScore1),[3](#RefFocusScore2)</sup>. We take the maximum change in focus as the starting point of each spheroid. 


### Summary

In the SphereDetect package, we provide solutions that works with images directly or with the output of a CellProfiler pipeline. In addition, we provide the link to the original Nikon JOBS, for those who have access to such a system. 
 
Wishlist: 
* full source 
* example (AZ data)
* pip package

We have not extensively tested the algorithm across system. We have gotten it to work for Nikon Spinning disk confocal, Molecular devices imageXpress, and XXX. We expect that this package works best on image data acquired by confocal microscopy. Any constructive feedback is appreciated! 

Notes: 
* We have been using the SYTO14 Cell Painting channel, but any channel that is bright will do.

References: 

<a name="Ref2025">1</a>: C. Ringers, D. Holmberg, *et al* High-content morphological profiling by Cell Painting in 3D spheroids. *BioRxiv*

<a name="RefFocusScore1">2</a>: [FocusScore](https://cellprofiler-manual.s3.amazonaws.com/CellProfiler-4.0.5/modules/measurement.html#:~:text=Measurements%20made%20by%20this%20module,-Blur%20metrics&text=FocusScore%3A%20A%20measure%20of%20the,scores%20correspond%20to%20lower%20bluriness)

<a name="RefFocusScore2">3</a>: [Normalized Variance](https://analyticalsciencejournals.onlinelibrary.wiley.com/doi/epdf/10.1002/jemt.20118)

<a name="NikonJOBS">4</a>: TODO: Add the algorithm implemented in Nikon JOBS. 

