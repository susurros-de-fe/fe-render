import React from 'react';
import {AbsoluteFill, Composition} from 'remotion';
import {DUR} from './kit';
import * as E from './Escena';

const FPS = 30;

// FE: solo la ilustracion animada. Voz, musica, subtitulos y acabado los agrega render_fe.py.
const Video: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: '#0b1020', overflow: 'hidden'}}>
    <E.Escena />
  </AbsoluteFill>
);

export const Root: React.FC = () => <Composition id={'Video'} component={Video} durationInFrames={Math.max(FPS, Math.ceil(DUR * FPS))} fps={FPS} width={1080} height={1920} />;
