import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os
import tifffile as tiff
import re

# --------------------------------------------------------------------------------------------------------------------
# Need to figure out these things: 
# --------------------------------------------------------------------------------------------------------------------

#TODO: Make this work for both types of input. 
# Cellprofiler output
image_path = '/share/data/cellprofiler/automation/results/AssayPlate_Corning_3830/5514/8903/featICF_Image.parquet',
# Folder raw images #TODO: find the folder path to raw images that I can access. 
image_path = '/mnt/external-images-pvc/spher-colo52-az/CellPainting_20241220clearedspheroidsBOMI_20241220_151510/AssayPlate_Corning_3830/'

#TODO: Take the following row out of the code. 
df = pd.read_parquet(image_path)
df['URL_SphereDetect'] = df['URL_SphereDetect'].str.replace(
    '/share/data/external-datasets/', 
    '/mnt/external-images-pvc/') # This is specific to the way the data is stored in our database

# TODO: Note somewhere that it would be best to have a metadata indicating slice or section or plane in the cellprofiler output. Fix it beforehand for the example.
#  df['Metadata_Z'] = df['FileName_SYTO'].str.extract(r'Z(\d+)C').astype(int) # Extract the Z slice number from the filename, there might be a better way to do this in the CellProfiler pipeline

#TODO: Make a normal setlist with Cellprofiler and see how it looks? 

# --------------------------------------------------------------------------------------------------------------------

class SphereDetect:
    """
    A module for detecting spheroids in confocal Z-stack image data.
    """
    
    def __init__(self): 
        self.data = None
        self.results = None

    def load_data(
            self: object,
            image_path: str,
            regex: str = None, 
            channel: str = None, 
            flag: str = 'cellprofiler',
            ): 
        """ Load relevant images for spheroid detection
        """

        valid_flags = ['raw_images', 'cellprofiler']
        if flag not in valid_flags:
            raise ValueError(f"Expected one of {valid_flags}, got '{flag}'.")

        # The path refers to a folder with raw images
        if flag == 'raw_images': 
            if not os.path.isdir(image_path): 
                raise ValueError(f"'{image_path}' is not a valid directory")
            
            if regex is None:
                raise ValueError("For 'raw_images', you must specify a 'regex'.")
            
            self.data = self.load_from_images(image_path, regex)

        # The path refers to a cellprofiler output
        elif flag == 'cellprofiler':
            if not os.path.isfile(image_path):
                "The image_path is not a valid file"
            
            valid_extensions = {".csv", ".parquet"}
            file_ext = os.path.splitext(image_path)[1].lower()
            if file_ext not in valid_extensions:
                raise ValueError(
                    f"Expected a CSV or parquet file (.csv/.parquet), got '{file_ext}' for '{image_path}'."
                    )
            
            if channel is None:
                raise ValueError("For 'cellprofiler', you must specify a 'channel'.")
            
            self.data = self.load_from_cp_output(image_path, channel)

    def load_from_images(self, image_path, regex): 
            """
            contructs a list of images from the folder containing raw images 
            image_path: str, 
                folder path to the raw images
            """
            image_list = []
            for root, dirs, files in os.walk(image_path):
                for x in files:
                     if x.endswith(".tif", ".tiff") and re.search(regex, x) : # assuming we have tif files and we match the regex
                        image_list.append(os.path.join(root, x))

            df = pd.DataFrame(image_list, columns=['image_path'])
            df['Metadata_Well, Metadata_Z'] = df['image_path'].str.extract(regex).astype(int)

            return df

    def load_from_cp_output(self, image_path, channel):

        if cellprofiler_output.endswith(".csv"):
            df = pd.read_csv(image_path)

        elif cellprofiler_output.endswith(".parquet"):
            df = pd.read_parquet(image_path)

        if f'URL_{channel.upper()}' not in df.columns:
            raise ValueError("The column f'URL_{channel.upper()}' is not present in the dataframe")


        # Rename the URL column to match the channel
        df = df.rename(columns={f'URL_{channel.upper()}': 'image_path'})

        # Only keep the relevant columns
        df = df[['Metadata_Well', 'Metadata_Z', 'image_path']]

        return df

    def detect_spheres(self, offset, fmin):
        """
        Detect spheroids in the image data, assign a plane number to each image, and filter out wells that do not meet the minimum focus score.
        """
        # df['image_path'] = df[channel].str.split(':').apply(lambda parts: ':'.join(parts[1:])) #TODO: remove this from here? 
              
        # Calculate the normalized variance for each image
        df['normalized_variance'] = df['image_path'].apply(lambda image: self.calculate_normalized_variance(self.read_image(image))) 

        # Caluclate the differential normalized variance
        df = (
            df.sort_values(['Metadata_Well', 'Metadata_Z'])
                .assign(delta_normalized_variance=lambda x: 
                    x.groupby('Metadata_Well')['normalized_variance'].diff())
        )

        # Assign the plane number to each image
        df = (
            df.sort_values(['Metadata_Well', 'Metadata_Z'])
                .groupby('Metadata_Well', group_keys=False)
                .apply(self.assign_plane)
        )

        # Assign the plane number to each image
        self.assign_plane(df, offset)

        # Filter out wells that do not meet the minimum focus score
        self.postprocess(df, fmin)

        self.result = df
    
    def read_image(self, image):
        with tiff.TiffFile(image) as tf:
            data = tf.asarray()
        return data

    def calculate_normalized_variance(self, data):
        return np.var(data) / np.mean(data)
    

    def assign_plane(self, group, offset):
        idxmax = group['delta_normalized_variance'].idxmax() 
        offset_x = group.index.get_loc(idxmax) + offset
        
        planes = (np.arange(len(group)) - offset_x)
        planes = np.where(planes < 0, pd.NA, planes) # Replace negative plane values (i.e. rows before max) with NaN; take a maximum plane limit?
        
        group['Metadata_Plane'] = pd.Series(planes, index=group.index, dtype='Int64')
        self.results = group

   
    def postprocess(self, df, fmin):
        """
        Discard any wells that do not meet the minimum focus score.
        """
       
        #Identify the wells that meet the condition for plane 0
        wells_of_interest = df.loc[
            (df['Metadata_Plane'] == 0) & (df['normalized_variance'] > fmin),
                'Metadata_Well'].unique()

        filtered_df = df[df['Metadata_Well'].isin(wells_of_interest)]
        
        self.results = filtered_df
    
    def visualize(self):
        """
        Visualize detected spheres, works on the results of the detect_spheres method.
        """
        df = self.results

        df = df.sort_values(by='Metadata_Z')
        df_grouped = df.groupby('Metadata_Well')

        # Then plot the normalized variance across Z for each well
        fig, ax = plt.subplots()
        for name, group in df_grouped:
            ax.plot(group['Metadata_Z'], group['d_normalized_variance'], label=name)

    
    def run(
            self: object, 
            regex: str = r'([A-P]\d{1,2})Z(\d+)C03', #TODO: is this the best way to do this?
            channel: str = 'SYTO',
            image_path: str = '/share/data/cellprofiler/automation/results/AssayPlate_Corning_3830/5514/8903/featICF_Image.parquet', 
            flag: str = 'cellprofiler', 
            offset: int = -2,
            fmin: float = 250,
            visualize : bool = False,
            ):
        """
        Run the full sphere detection pipeline.

        Parameters
        ----------
        flag : str, default 'cellprofiler'
            is it a folder you are providing or a cellprofiler output?  
            currently supports one of ['raw_images', 'cellprofiler']
        path_to_images: string? 
            a path to the folder with images or a path to the cellprofiler output
        regex : str, default r'Z(\d+)C03'
            pattern that can collect metadata from the images. Only is CellProfiler data is not provided.
        channel : str, default 'SYTO'
            channel to perform detection on, needs to match the channelname in the cellprofiler output.
        cellprofiler_output : 
            path to cellprofiler output, should take both csv and parquet
        image_path : 
            directory of all your raw images. 
        offset : int, default -2
            value to offset the starting plane. Subtracting 2 works well in our case.
        fmin : float, default 250
            minimum value for the focus score at the maximum change. In practice this will help weed out some non-spheroid images, or poor qualiy spheroids. 
            likely needs to be calibrated for each setup, and assay. 
        visualize : Boolean, default False
            True or False
        """
        self.load_data(flag, image_path, channel, regex)

        results = self.detect_spheres()
        
        # df = pd.read_parquet(cellprofiler_output)
        # self.preprocess()
        # self.preprocess(self, channel)
    
        # df['URL_SphereDetect'] = df[channel].str.split(':').apply(lambda parts: ':'.join(parts[1:]))
        # df['Metadata_Z'] = df['FileName_SYTO'].str.extract(r'Z(\d+)C').astype(int) # Extract the Z slice number from the filename, there might be a better way to do this in the CellProfiler pipeline
        # df['URL_SphereDetect'] = df['URL_SphereDetect'].str.replace('/share/data/external-datasets/', '/mnt/external-images-pvc/') # This is specific to the way the data is stored in our database
        # df['normalized_variance'] = df['URL_SphereDetect'].apply(lambda image: self.calculate_normalized_variance(self.read_image(image)))
        
        if visualize: 
            self.visualize()

        return results


# --------------------------------------------------------------------------------------------------------------------
# Example usage 
if __name__ == "__main__":
    detector = SphereDetect()
    detected_spheres = detector.run(
        regex="some_regex_pattern",
        channel="URL_SYTO",
        image_path="/path/to/your/parquet/or/folder",
        flag="cellprofiler",  # or "raw_images"
        offset=-2,
        fmin=250,
        visualize=False
    )

    print(detected_spheres)

