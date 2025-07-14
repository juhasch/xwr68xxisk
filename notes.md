

https://dev.ti.com/gallery/view/6023734/mmWave_Demo_Visualizer_Record/ver/3.2.0/
https://dev.ti.com/gallery/view/1792614/mmWaveSensingEstimator/ver/1.3.0/


### Size calculation

1 	cmplx16ImRe_t x[numTXPatterns][numDopplerChirps][numRX][numRangeBins] 	1D Range FFT output
2 	cmplx16ImRe_t x[numRangeBins][numDopplerChirps][numTXPatterns][numRX] 	1D Range FFT output
3 	cmplx16ImRe_t x[numRangeBins][numTXPatterns][numRX][numDopplerChirps] 	1D Range FFT output
4 	cmplx16ImRe_t x[numRangeBins][numDopplerBins][numTXPatterns][numRX] 	2D (Range+Doppler) FFT output
5 	cmplx16ImRe_t x[numRangeBins][numTXPatterns][numRX][numDopplerBins] 	2D (Range+Doppler) FFT output

