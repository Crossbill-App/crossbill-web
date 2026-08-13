import { RouterProvider, createRouter } from '@tanstack/react-router';
import { routerOptions } from './router';

const router = createRouter(routerOptions);

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

function App() {
  return <RouterProvider router={router} />;
}

export default App;
