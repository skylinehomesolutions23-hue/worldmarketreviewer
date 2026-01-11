import { StatusBar } from '@capacitor/status-bar';

window.addEventListener('load', async () => {
  try {
    await StatusBar.hide();
  } catch (e) {
    console.log('StatusBar plugin not available in browser');
  }
});
