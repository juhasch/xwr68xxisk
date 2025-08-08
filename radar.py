# Temporary fix for frame period
# replace 5th argument with framePeriod
if line.startswith('frameCfg'):
    parts = line.split()
    parts[4] = str(int(self.radar_params['framePeriod']))
    line = ' '.join(parts)
    self.frame_period = self.radar_params['framePeriod']

# Temporary fix for clutterRemoval
if line.startswith('clutterRemoval'):
    line = 'clutterRemoval -1 ' + ('1' if self.radar_params['clutterRemoval'] else '0') + '\n'
    self._clutter_removal = self.radar_params['clutterRemoval']

# Temporary fix for multiObjBeamForming
if line.startswith('multiObjBeamForming'):
    parts = line.split()
    parts[1] = '1' if self.radar_params['multiObjBeamForming'] else '0'
    line = ' '.join(parts)
    self._multi_obj_beam_forming = self.radar_params['multiObjBeamForming']

# Temporary fix for multiObjBeamForming