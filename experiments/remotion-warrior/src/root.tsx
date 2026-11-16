import React from 'react';
import {Composition} from 'remotion';
import {WarriorShort} from './warrior';
export const Root: React.FC = () => <Composition id="WarriorShort" component={WarriorShort} durationInFrames={150} fps={30} width={1080} height={1920}/>;
