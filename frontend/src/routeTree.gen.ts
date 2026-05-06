import { rootRoute } from "@/routes/__root";
import { indexRoute } from "@/routes/index";
import { replyRecordsRoute } from "@/routes/reply-records";
import { replyStrategiesRoute } from "@/routes/reply-strategies";
import { reviewsRoute } from "@/routes/reviews";
import { taskQueueRoute } from "@/routes/task-queue";
import { tasksRoute } from "@/routes/tasks";
import { usersRoute } from "@/routes/users";

export const routeTree = rootRoute.addChildren([
  indexRoute,
  reviewsRoute,
  replyStrategiesRoute,
  tasksRoute,
  taskQueueRoute,
  replyRecordsRoute,
  usersRoute
]);
