#!/usr/bin/env node

import { execSync, spawn } from 'child_process';
import { platform } from 'os';
import { join, resolve } from 'path';
import { fileURLToPath } from 'url';
import { existsSync } from 'fs';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const backendDir = resolve(__dirname, '..', 'backend');
const isWindows = platform() === 'win32';

/**
 * Get the Python executable from the venv
 * Checks for both .venv (uv) and venv (standard) directories
 */
function getVenvPython() {
  const venvDirs = ['.venv', 'venv'];
  
  for (const venvName of venvDirs) {
    const venvDir = join(backendDir, venvName);
    let pythonPath;
    if (isWindows) {
      pythonPath = join(venvDir, 'Scripts', 'python.exe');
    } else {
      pythonPath = join(venvDir, 'bin', 'python');
    }
    
    if (existsSync(pythonPath)) {
      return pythonPath;
    }
  }
  
  // If no venv found, return default path (will fail with helpful error)
  return isWindows 
    ? join(backendDir, 'venv', 'Scripts', 'python.exe')
    : join(backendDir, 'venv', 'bin', 'python');
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
      console.error('❌ Virtual environment not found.');
      console.error('   Run: npm run setup:backend');
      console.error('   Or manually: cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt');
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

