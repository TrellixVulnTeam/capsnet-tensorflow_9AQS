import time
import utils
import tensorflow as tf
import numpy as np
from tqdm import tqdm
from capsNet import CapsNet
from config import cfg


class Main(object):

    def __init__(self, model):
        """
        Load data and initialize model.
        :param model: the model which will be trained
        """

        # Global start time
        self.start_time = time.time()

        # Load data
        utils.thick_line()
        print('Loading data...')
        utils.thin_line()
        x_train = utils.load_data_from_pickle('./data/source_data/mnist/train_image.p')
        x_train = x_train.reshape([-1, 28, 28, 1])
        self.x_valid = x_train[55000:60000]
        assert self.x_valid.shape == (5000, 28, 28, 1), self.x_valid.shape
        self.x_train = x_train[:55000]
        assert self.x_train.shape == (55000, 28, 28, 1), self.x_train.shape
        y_train = utils.load_data_from_pickle('./data/source_data/mnist/train_label.p')
        self.y_valid = y_train[55000:60000]
        assert self.y_valid.shape == (5000, 10), self.y_valid.shape
        self.y_train = y_train[:55000]
        assert self.y_train.shape == (55000, 10), self.y_train.shape
        self.n_batch_train = 55000 // cfg.BATCH_SIZE
        self.n_batch_valid = 5000 // cfg.BATCH_SIZE

        # Build graph
        utils.thick_line()
        print('Building graph...')
        self.train_graph, self.inputs, self.labels, self.cost, self.optimizer, self.accuracy = \
            model.build_graph(image_size=self.x_train.shape[1:], num_class=self.y_train.shape[1])

    @staticmethod
    def _get_batches(x, y):
        """ Split features and labels into batches."""
        for start in range(0, len(x)-cfg.BATCH_SIZE, cfg.BATCH_SIZE):
            end = start + cfg.BATCH_SIZE
            yield x[start:end], y[start:end]

    def _display_status(self, sess, x_batch, y_batch, epoch_i, batch_counter):
        """Display information during training."""

        valid_batch_idx = np.random.choice(range(len(self.x_valid)), cfg.BATCH_SIZE).tolist()
        x_valid_batch = self.x_valid[valid_batch_idx]
        y_valid_batch = self.y_valid[valid_batch_idx]

        cost_train, acc_train = sess.run([self.cost, self.accuracy],
                                         feed_dict={self.inputs: x_batch, self.labels: y_batch})
        cost_valid, acc_valid = sess.run([self.cost, self.accuracy],
                                         feed_dict={self.inputs: x_valid_batch, self.labels: y_valid_batch})

        print('Epoch: {}/{} |'.format(epoch_i + 1, cfg.EPOCHS),
              'Batch: {} |'.format(batch_counter),
              'Time: {:.2f}s |'.format(time.time() - self.start_time),
              'Train_Loss: {:.4f} |'.format(cost_train),
              'Train_Accuracy: {:.2f}% |'.format(acc_train * 100),
              'Valid_Loss: {:.4f} |'.format(cost_valid),
              'Valid_Accuracy: {:.2f}% |'.format(acc_valid * 100))

    def _add_summaries(self, sess, train_writer, valid_writer, merged, x_batch, y_batch, batch_counter):
        """Add summaries to TensorBoard while training."""

        valid_batch_idx = np.random.choice(range(len(self.x_valid)), cfg.BATCH_SIZE).tolist()
        x_valid_batch = self.x_valid[valid_batch_idx]
        y_valid_batch = self.y_valid[valid_batch_idx]

        summary_train = sess.run(merged, feed_dict={self.inputs: x_batch, self.labels: y_batch})
        train_writer.add_summary(summary_train, batch_counter)
        summary_valid = sess.run(merged, feed_dict={self.inputs: x_valid_batch, self.labels: y_valid_batch})
        valid_writer.add_summary(summary_valid, batch_counter)

    def _print_full_set_eval(self, sess, epoch_i, batch_counter):
        """Evaluate on the full data set and print information."""

        eval_start_time = time.time()

        utils.thin_line()
        print('Calculating losses using full data set...')
        cost_train_all = []
        cost_valid_all = []
        acc_train_all = []
        acc_valid_all = []

        if cfg.EVAL_WITH_FULL_TRAIN_SET:
            utils.thin_line()
            print('Calculating loss and accuracy on full train set...')
            _train_batch_generator = self._get_batches(self.x_train, self.y_train)
            for _ in tqdm(range(self.n_batch_train), total=self.n_batch_train, ncols=100, unit='batch'):
                train_batch_x, train_batch_y = next(_train_batch_generator)
                cost_train_i, acc_train_i = \
                    sess.run([self.cost, self.accuracy],
                             feed_dict={self.inputs: train_batch_x, self.labels: train_batch_y})
                cost_train_all.append(cost_train_i)
                acc_train_all.append(acc_train_i)

        utils.thin_line()
        print('Calculating loss and accuracy on full valid set...')
        _valid_batch_generator = self._get_batches(self.x_valid, self.y_valid)
        for _ in tqdm(range(self.n_batch_valid), total=self.n_batch_valid, ncols=100, unit='batch'):
            valid_batch_x, valid_batch_y = next(_valid_batch_generator)
            cost_valid_i, acc_valid_i = \
                sess.run([self.cost, self.accuracy],
                         feed_dict={self.inputs: valid_batch_x, self.labels: valid_batch_y})
            cost_valid_all.append(cost_valid_i)
            acc_valid_all.append(acc_valid_i)
        print('Evaluation done! Using time: {:.2f}'.format(time.time() - eval_start_time))

        cost_train = sum(cost_train_all) / len(cost_train_all)
        cost_valid = sum(cost_valid_all) / len(cost_valid_all)
        acc_train = sum(acc_train_all) / len(acc_train_all)
        acc_valid = sum(acc_valid_all) / len(acc_valid_all)

        utils.thin_line()
        print('Epoch: {}/{} |'.format(epoch_i + 1, cfg.EPOCHS),
              'Batch: {} |'.format(batch_counter),
              'Time: {:.2f}s |'.format(time.time() - self.start_time))
        utils.thin_line()
        if cfg.EVAL_WITH_FULL_TRAIN_SET:
            print('Full_Set_Train_Loss: {:.4f}\n'.format(cost_train),
                  'Full_Set_Train_Accuracy: {:.2f}%'.format(acc_train * 100))
        print('Full_Set_Valid_Loss: {:.4f}\n'.format(cost_valid),
              'Full_Set_Valid_Accuracy: {:.2f}%'.format(acc_valid*100))

    def train(self):
        """Training model."""

        with tf.Session(graph=self.train_graph) as sess:

            utils.thick_line()
            print('Training...')

            # Merge all the summaries and create writers
            merged = tf.summary.merge_all()
            train_log_path = cfg.LOG_PATH + '/train'
            valid_log_path = cfg.LOG_PATH + '/valid'
            utils.check_dir([cfg.LOG_PATH, train_log_path, valid_log_path])
            train_writer = tf.summary.FileWriter(train_log_path, sess.graph)
            valid_writer = tf.summary.FileWriter(valid_log_path)

            sess.run(tf.global_variables_initializer())
            batch_counter = 0

            for epoch_i in range(cfg.EPOCHS):

                epoch_start_time = time.time()
                utils.thick_line()
                print('Training on epoch: {}/{}'.format(epoch_i+1, cfg.EPOCHS))

                if cfg.DISPLAY_STEP is not None:
                    for x_batch, y_batch in self._get_batches(self.x_train, self.y_train):

                        batch_counter += 1

                        # Training optimizer
                        sess.run(self.optimizer, feed_dict={self.inputs: x_batch, self.labels: y_batch})

                        if batch_counter % cfg.DISPLAY_STEP == 0:
                            self._display_status(sess, x_batch, y_batch, epoch_i, batch_counter)

                        if cfg.SUMMARY_STEP is not None:
                            if batch_counter % cfg.SUMMARY_STEP == 0:
                                self._add_summaries(sess, train_writer, valid_writer, merged,
                                                    x_batch, y_batch, batch_counter)
                else:
                    utils.thin_line()
                    train_batch_generator = self._get_batches(self.x_train, self.y_train)
                    for _ in tqdm(range(self.n_batch_train), total=self.n_batch_train, ncols=100, unit='batch'):

                        batch_counter += 1
                        x_batch, y_batch = next(train_batch_generator)

                        # Training optimizer
                        sess.run(self.optimizer, feed_dict={self.inputs: x_batch, self.labels: y_batch})

                        if cfg.SUMMARY_STEP is not None:
                            if batch_counter % cfg.SUMMARY_STEP == 0:
                                self._add_summaries(sess, train_writer, valid_writer, merged,
                                                    x_batch, y_batch, batch_counter)

                if cfg.FULL_SET_EVAL_STEP is not None:
                    if (epoch_i+1) % cfg.FULL_SET_EVAL_STEP == 0:
                        self._print_full_set_eval(sess, epoch_i, batch_counter)

                utils.thin_line()
                print('Epoch done! Using time: {:.2f}'.format(time.time() - epoch_start_time))

        utils.thick_line()
        print('Done! Total time: {:.2f}'.format(time.time() - self.start_time))
        utils.thick_line()


if __name__ == '__main__':

    CapsNet_ = CapsNet()
    Main_ = Main(CapsNet_)
    Main_.train()
