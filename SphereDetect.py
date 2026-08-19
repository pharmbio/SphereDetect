import pandas as pd
import numpy as np
import os
import tifffile as tiff
import re
from concurrent.futures import ThreadPoolExecutor


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
            # z_info : str = 'Metadata_Plane'
            ): 
        """ Load relevant images for spheroid detection
        """

        # Option 1: Load from raw images
        if os.path.isdir(image_path):
            if regex is None:
                raise ValueError("For folder-based loading, you must specify a 'regex'.")
            self.data = self.load_from_images(image_path, regex)
    
        # Option 2: Load from CellProfiler output
        else:
            if not os.path.isfile(image_path):
                raise ValueError(f"'{image_path}' is not a valid file or directory.")
            
            valid_extensions = {".csv", ".parquet"}
            file_ext = os.path.splitext(image_path)[1].lower()
            if file_ext not in valid_extensions:
                raise ValueError(
                    f"Expected a CSV or parquet file (.csv/.parquet), got '{file_ext}' for '{image_path}'."
                )
            
            if channel is None:
                raise ValueError("For CellProfiler outputs, you must specify a 'channel'.")
        
            self.data = self.load_from_cp_output(image_path, channel)

        assert self.data is not None, "The data is not loaded"

    def load_from_images(self, image_path, regex): 
            """
            contructs a list of images from the folder containing raw images 
            image_path: str, 
                folder path to the raw images
            """
            image_list = []
            for root, dirs, files in os.walk(image_path):
                for x in files:
                     if x.endswith((".tif", ".tiff")) and re.search(regex, x) : # assuming we have tif files and we match the regex
                        image_list.append(os.path.join(root, x))

            df = pd.DataFrame(image_list, columns=['image_path'])
            df[["Metadata_Well", "Metadata_Z"]] = df['image_path'].str.extract(regex).reset_index(drop=True) 
            df["Metadata_Z"] = df["Metadata_Z"].astype(int) 
            return df

    def load_from_cp_output(self, image_path, channel):

        if image_path.endswith(".csv"):
            df = pd.read_csv(image_path)

        elif image_path.endswith(".parquet"):
            df = pd.read_parquet(image_path)

        assert df is not None, "The dataframe is not loaded"

        if f'PathName_{channel.upper()}' not in df.columns:
            raise ValueError("The column f'PathName_{channel.upper()}' is not present in the dataframe")

        df['image_path'] = df.apply(lambda row: os.path.join(row[f'PathName_{channel.upper()}'], 
                                                             row[f'FileName_{channel.upper()}']),axis=1)
        df['Metadata_Z'] = df[self.z_info].astype(int) 
        df = df[['image_path','Metadata_Well', 'Metadata_Z']].reset_index(drop=True)
        return df

    def detect_spheres(self):
        """
        Detect spheroids in the image data, assign a plane number to each image, and filter out wells that do not meet the minimum focus score.
        """
        df = self.data

        with ThreadPoolExecutor(max_workers=8) as executor:
            variances = list(executor.map(self.compute_norm_variance, df['image_path']))
        df['normalized_variance'] = variances

        # Caluclate the differential normalized variance
        df = df.sort_values(['Metadata_Well', 'Metadata_Z'])

        # Assign the plane number to each image
        df['delta_normalized_variance'] = df.groupby('Metadata_Well')['normalized_variance'].diff()
        # Select the columns explicitly so the grouping key survives the apply. pandas 3.0
        # excludes grouping columns from the applied frame (2.x only warned), which dropped
        # Metadata_Well before postprocess could filter on it.
        df = df.groupby('Metadata_Well', group_keys=False)[df.columns.tolist()].apply(
            lambda group: self.assign_plane(group))


        # Filter out wells that do not meet the minimum focus score
        self.postprocess(df)
        assert df is not None, "The dataframe is not loaded"
        self.result = df
    
    def read_image(self, image): 
        with tiff.TiffFile(image) as tf:
            data = tf.asarray()
        if self.downsample > 1: # Assume the image is 2D
            data = data[::self.downsample, ::self.downsample]
        return data

    def calculate_normalized_variance(self, data):
        return np.var(data) / np.mean(data)
    
    def compute_norm_variance(self, image_path):
        img = self.read_image(image_path)
        return self.calculate_normalized_variance(img)


    def assign_plane(self, group):
        idxmax = group['delta_normalized_variance'].idxmax() 
        offset_x = group.index.get_loc(idxmax) + self.offset
        
        planes = (np.arange(len(group)) - offset_x)
        planes = np.where(planes < 0, pd.NA, planes) # Replace negative plane values (i.e. rows before max) with NaN; take a maximum plane limit?
        
        group['Metadata_Z_calculated'] = pd.Series(planes, index=group.index, dtype='Int64')
        return group

   
    def postprocess(self, df):
        """
        Discard any wells that do not meet the minimum focus score.
        """
       
        #Identify the wells that meet the condition for plane 0
        wells_of_interest = df.loc[
            (df['Metadata_Z_calculated'] == 0) & (df['normalized_variance'] > self.fmin),
                'Metadata_Well'].unique()

        filtered_df = df[df['Metadata_Well'].isin(wells_of_interest)]
        
        self.results = filtered_df
    
    def visualize(self):
        """
        Visualize detected spheres, works on the results of the detect_spheres method.
        """
        import matplotlib.pyplot as plt

        ### Plot the normalized variance across Z for each well        
        df_plot = self.results

        # Group df by Metadata_Well and sort by Metadata_Z
        df_grouped = df_plot.sort_values(by='Metadata_Z').groupby('Metadata_Well')

        # Then plot the normalized variance across Z for each well
        fig, ax = plt.subplots()
        for name, group in df_grouped:
            ax.plot(group['Metadata_Z'], group['normalized_variance'], label=name)
        ax.set_xlabel('Z')
        ax.set_ylabel('Normalized Variance')
        ax.set_title('Normalized Variance across Z for each well')

    def run(
            self: object, 
            regex: str,
            channel: str,
            image_path: str, 
            z_info : str = 'Metadata_Plane',
            offset: int = -2,
            fmin: float = 250,
            downsample : int = 4,
            visualize : bool = False,
            ):
        """
        Run the full sphere detection pipeline.

        Parameters
        ----------
        regex : str, default r'Z(\d+)C03'
            pattern that can collect metadata from the images. Only is CellProfiler data is not provided.
        channel : str, default 'SYTO'
            channel to perform detection on, needs to match the channelname in the cellprofiler output. 
        image_path : 
            folder containing all raw images or path to cellprofiler output, takes both csv and parquet 
        z_info : str, default 'Metadata_Site'
            column name in the cellprofiler output that contains the Z/plane/section information. 
            If you are using raw images, this will be ignored.
        offset : int, default -2
            value to offset the starting plane. Subtracting 2 works well in our case.
        fmin : float, default 250
            minimum value for the focus score at the maximum change. In practice this will help weed out some non-spheroid images, or poor qualiy spheroids. 
            likely needs to be calibrated for each setup, and assay. 
        visualize : Boolean, default False
            True or False
        """

        # Set class variables
        self.z_info = z_info
        self.offset = offset
        self.fmin = fmin
        self.downsample = downsample

        # Load the data
        self.load_data(image_path, regex, channel)
        
        # Detect the spheroids
        self.detect_spheres() 

        # Visualize the results       
        if visualize: 
            self.visualize()

        return self.results


# --------------------------------------------------------------------------------------------------------------------
# Example usage 
if __name__ == "__main__":
    detector = SphereDetect()
    detected_spheres = detector.run( 
        regex = r'([A-P]\d{1,2})_T0001F001L01A03Z(\d+)C03', #TODO: is this the best way to do this?
        channel = 'SYTO',
        image_path = '/mnt/external-images-pvc/spher-colo52-az/CellPainting_20241220clearedspheroidsBOMI_20241220_151510/AssayPlate_Corning_3830/', 
        # image_path = '/home/jovyan/share/data/analyses/christa/SphereDetect/cp_output.parquet',
        z_info = 'Metadata_Plane',
        offset = -2,
        fmin = 250,
        downsample = 4, 
        visualize = True,
)

    print(detected_spheres)

