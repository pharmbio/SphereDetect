# SphereDetect

#TODO: Add a nice image

Imaging spheroids in high-content assays can lead to collecting a lot of empty data. Especially finding a spheroids starting point can be challenging. There are ways to do it, but most of them are proprietary and specific to the microscope system. 

Here we present SphereDetect, which implements a an algorithm to automatically detect the first spheroid section in a Z-stack. The algorithm relies on a spheroid coming into focus as one starts imaging in Z. Specifically, it finds the maximum change in FocusScore (ref1+ref2).  

### Summary

In the SphereDetect package, we provide solutions that works with images directly or with the output of a CellProfiler pipeline. In addition, we provide the link to the original Nikon JOBS, for those who have access to such a system. 
 
Wishlist: 
* full source 
* example (AZ data)
* pip package

We have not extensively tested the algorithm across system. We have gotten it to work for Nikon Spinning disk confocal, Molecular devices imageXpress, and XXX. We expect that this package works best on image data acquired by confocal microscopy. Any constructive feedback is appreciated! 


References: 
* The paper 
* The algorithm implemented in Nikon JOBS. 
* Original paper 1
* Original paper 2




