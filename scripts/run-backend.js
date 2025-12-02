#!/usr/bin/env node

import { execSync, spawn } from 'child_process';
import { platform } from 'os';
import { join, resolve } from 'path';
import { fileURLToPath } from 'url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const backendDir = resolve(__dirname, '..', 'backend');
const venvDir = join(backendDir, '.venv');
const isWindows = platform() === 'win32';

/**
 * Get the Python executable from the venv
 */
function getVenvPython() {
  if (isWindows) {
    return join(venvDir, 'Scripts', 'python.exe');
  } else {
    return join(venvDir, 'bin', 'python');
  }
}

/**
 * Run uvicorn with the venv Python
 */
function runBackend() {
  const pythonPath = getVenvPython();
  
  console.log('Starting backend server...');
  
  // Spawn uvicorn as a child process
  const args = ['-m', 'uvicorn', 'app.main:app', '--reload'];
  const uvicorn = spawn(pythonPath, args, {
    cwd: backendDir,
    stdio: 'inherit',
    shell: false
  });

  uvicorn.on('error', (error) => {
    console.error(`Failed to start server: ${error.message}`);
    if (error.code === 'ENOENT') {
      console.error('Virtual environment not found. Run: npm run setup:backend');
    }
    process.exit(1);
  });

  uvicorn.on('exit', (code) => {
    process.exit(code || 0);
  });

  // Handle termination signals
  process.on('SIGINT', () => {
    uvicorn.kill('SIGINT');
  });
  
  process.on('SIGTERM', () => {
    uvicorn.kill('SIGTERM');
  });
}

runBackend();

