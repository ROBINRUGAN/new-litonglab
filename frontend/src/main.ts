// designed by mew
import { createApp } from 'vue';
import { pinia } from './stores';
import { router } from './router';
import App from './App.vue';
import { editDirective } from './editor/target';
import './styles/style.css';
import './styles/themes.css';
import './styles/refinements.css';
import './styles/content.css';

createApp(App).use(pinia).use(router).directive('edit', editDirective).mount('#app');
